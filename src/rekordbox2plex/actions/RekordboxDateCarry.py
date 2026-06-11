import os
from typing import Dict, List, Optional, Tuple

from rich.panel import Panel
from rich.table import Table

from ._ActionBase import ActionBase
from ..config import (
    get_db_path,
    get_lossless_exts,
    get_lossy_exts,
    get_music_root,
    get_plex_media_path_map,
    get_rb_added_at_field,
    get_rb_date_backup_dir,
    get_rb_date_snapshot_path,
    get_rb_dates_mode,
    get_stability_wait,
    should_allow_running,
    should_ignore_case,
    should_ignore_wal,
    should_keep_applied,
    should_write,
)
from ..rekordbox.date_snapshot import capture_dates
from ..rekordbox.RekordboxDBWriter import RekordboxDBWriter
from ..rekordbox.resolvers.added_at import read_rb_added_at_raw
from ..rekordbox.resolvers.track import resolve_rb_id_by_host_path
from ..utils import snapshot_store
from ..utils.snapshot_store import SnapshotEntry, SnapshotStore
from ..utils.confirm import confirm_destructive
from ..utils.logger import console, logger
from ..utils.media_paths import parse_media_path_map
from ..utils.pairing import walk_pairs
from ..utils.paths import PROJECT_ROOT
from ..utils.rb_db_safety import (
    DBNotQuiescent,
    assert_db_quiescent,
    backup_rekordbox_db,
)


def _fmt(value: object) -> str:
    if value is None or value == "":
        return "[dim]—[/dim]"
    return str(value)


class RekordboxDateCarry(ActionBase):
    """Preserve the Rekordbox "Date Added" across a lossy→lossless file swap.

    ``snapshot`` (read-only) records each lossy file's ``created_at`` keyed by the
    lossless path. ``apply`` (read-only unless ``--write``) restores it onto the
    re-added lossless row — the sanctioned, heavily-guarded Rekordbox write."""

    def __init__(self) -> None:
        super().__init__("rekordbox date carry")
        self.mode = get_rb_dates_mode()
        self.root = get_music_root()
        self.lossy_exts = get_lossy_exts()
        self.lossless_exts = get_lossless_exts()
        self.ignore_case = should_ignore_case()
        self.field = get_rb_added_at_field()
        self.snapshot_file = get_rb_date_snapshot_path()
        self.path_map = parse_media_path_map(get_plex_media_path_map())

    def run(self) -> None:
        if self.mode == "snapshot":
            self.snapshot()
        elif self.mode == "apply":
            self.apply()
        else:  # pragma: no cover - argparse constrains the choices
            logger.error(f"[red]Unknown rb-dates mode: {self.mode!r}")

    # --- snapshot ----------------------------------------------------------

    def snapshot(self) -> None:
        if not self.root or not os.path.isdir(self.root):
            logger.error(
                "[red]snapshot needs a valid music root — pass --root <dir> or set "
                "MUSIC_ROOT."
            )
            return
        pairs, _unmatched, _ambiguous = walk_pairs(
            self.root, self.lossy_exts, self.lossless_exts, self.ignore_case
        )
        entries, skipped = capture_dates(pairs, self.path_map, self.field)

        console.print(
            f"[bold cyan]{'Dry run — ' if self.dry_run else ''}Snapshot[/bold cyan] "
            f"root={self.root} field={self.field} "
            f"→ {self.snapshot_file}\n"
        )
        self._print_capture_table(entries)
        self._print_skipped(skipped, noun="lossy file")

        if not entries:
            console.print("[bold green]✔ Nothing to snapshot.")
            return
        if self.dry_run:
            console.print(
                f"\n[dim]Dry run — {len(entries)} date(s) NOT written to "
                f"{self.snapshot_file}. Re-run without --dry-run to save.[/dim]"
            )
            return
        store = snapshot_store.load(self.snapshot_file)
        changed = sum(
            snapshot_store.merge_entry(store, k, v) for k, v in entries.items()
        )
        snapshot_store.save(self.snapshot_file, store)
        console.print(
            f"\n[bold green]✔ Saved {len(entries)} snapshot(s) "
            f"({changed} new/changed) → {self.snapshot_file}[/bold green]"
        )

    def _print_capture_table(self, entries: Dict[str, SnapshotEntry]) -> None:
        if not entries:
            return
        table = Table(title="Rekordbox dates captured (keyed by lossless file)")
        table.add_column("#", justify="right", style="dim")
        table.add_column(f"{self.field} (preserved)", style="green")
        table.add_column("Lossless file", style="dim", overflow="fold")
        for i, (lossless, e) in enumerate(sorted(entries.items()), 1):
            table.add_row(str(i), _fmt(e["value"]), lossless)
        console.print(table)

    # --- apply -------------------------------------------------------------

    def apply(self) -> None:
        store = snapshot_store.load(self.snapshot_file)
        if not store:
            logger.info(
                f"[yellow]No snapshots in {self.snapshot_file} — run "
                f"`rb-dates snapshot` (or lossless-tags --snapshot-dates) first."
            )
            return

        # Resolve each lossless path to its (re-added) Rekordbox row.
        planned: List[Tuple[str, SnapshotEntry, int, Optional[str]]] = []  # +rb_id,cur
        pending: List[Tuple[str, str]] = []  # not re-added yet (keep in store)
        for lossless, entry in sorted(store.items()):
            rb_id = resolve_rb_id_by_host_path(lossless, self.path_map)
            if rb_id is None:
                pending.append((lossless, "not in Rekordbox yet — re-add it first"))
                continue
            current = read_rb_added_at_raw(rb_id, entry.get("rb_field", self.field))
            planned.append((lossless, entry, rb_id, current))

        console.print(
            f"[bold cyan]{'Dry run — ' if not should_write() else ''}Apply[/bold cyan] "
            f"from {self.snapshot_file} (field={self.field})\n"
        )
        self._print_apply_table(planned)
        self._print_skipped(pending, noun="lossless file")

        actionable = [p for p in planned if p[3] != p[1]["value"]]
        if not should_write():
            already = len(planned) - len(actionable)
            console.print(
                f"\n[bold]Would restore:[/bold] {len(actionable)}   "
                f"[bold]already correct:[/bold] {already}   "
                f"[bold]awaiting re-add:[/bold] {len(pending)}"
            )
            if actionable:
                console.print(
                    "\n[dim]Dry run — no DB changes. Re-run with --write to apply.[/dim]"
                )
            return

        if not actionable:
            logger.info("[green]Nothing to restore — every re-added row is correct.")
            self._maybe_prune(store, [p[0] for p in planned])
            return

        self._write(store, actionable)

    def _print_apply_table(
        self, planned: List[Tuple[str, SnapshotEntry, int, Optional[str]]]
    ) -> None:
        if not planned:
            return
        table = Table(title="Date restore plan (Rekordbox)")
        table.add_column("#", justify="right", style="dim")
        table.add_column("rb ID", justify="right", style="dim")
        table.add_column("Current (now)", style="red")
        table.add_column(f"Restore {self.field}", style="green")
        table.add_column("Lossless file", style="dim", overflow="fold")
        for i, (lossless, entry, rb_id, current) in enumerate(planned, 1):
            same = current == entry["value"]
            table.add_row(
                str(i),
                str(rb_id),
                "[dim]= target[/dim]" if same else _fmt(current),
                _fmt(entry["value"]),
                lossless,
            )
        console.print(table)

    # --- the guarded write -------------------------------------------------

    def _write(
        self,
        store: SnapshotStore,
        actionable: List[Tuple[str, SnapshotEntry, int, Optional[str]]],
    ) -> None:
        db_path = get_db_path()
        n = len(actionable)
        console.print(
            Panel(
                "[bold]Before writing the Rekordbox database, FREE UP THE DB:[/bold]\n"
                "  • Close Rekordbox on [red]every[/red] workstation (a clean close "
                "checkpoints the WAL).\n"
                "  • Pause Resilio Sync (or confirm it is idle) so it doesn't sync a "
                "half-written file or make conflict copies.\n"
                "  • Make sure nothing else has master.db open.\n\n"
                f"This will restore {self.field} on [red]{n}[/red] track(s) at "
                f"{db_path}.",
                title="⚠ Rekordbox write",
                border_style="red",
            )
        )
        if not confirm_destructive(
            f"This writes {n} Date-Added value(s) into the Rekordbox database.",
            "WRITE-RB-DATES",
            title="Write Rekordbox Dates",
        ):
            logger.info("[yellow]Aborted — confirmation token did not match.")
            return

        # Quiescence guard (skippable only via --allow-running for scratch copies).
        try:
            assert_db_quiescent(
                db_path,
                wait_seconds=get_stability_wait(),
                ignore_wal=should_ignore_wal(),
                allow_running=should_allow_running(),
            )
        except DBNotQuiescent as e:
            logger.error(f"[red]Refusing to write — {e}")
            return

        backup_dir = get_rb_date_backup_dir() or str(
            PROJECT_ROOT / "rekordbox-db-backups"
        )
        backup = backup_rekordbox_db(db_path, backup_dir)
        console.print(f"[dim]Backed up master.db → {backup}[/dim]")

        rows = [(rb_id, entry["value"]) for _path, entry, rb_id, _cur in actionable]
        try:
            with RekordboxDBWriter() as writer:
                result = writer.apply_date_updates(rows, self.field)
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"[red]Write failed: {e}\n"
                f"[red]The database is unchanged on error; a backup is at {backup}."
            )
            return

        console.print(
            f"[bold green]✔ Restored {result['applied']} date(s) "
            f"({result['skipped']} already correct). "
            f"New localUpdateCount: {result['final_usn']}.[/bold green]"
        )
        self._maybe_prune(store, [p[0] for p in actionable])
        console.print(
            "\n[bold yellow]Keep Rekordbox closed on every workstation until "
            "Resilio has propagated master.db to all nodes[/bold yellow], then "
            "verify the dates and resume Resilio."
        )

    def _maybe_prune(self, store: SnapshotStore, applied_keys: List[str]) -> None:
        if should_keep_applied():
            return
        removed = snapshot_store.prune(store, applied_keys)
        if removed:
            snapshot_store.save(self.snapshot_file, store)
            console.print(
                f"[dim]Pruned {removed} applied entry(ies) from "
                f"{self.snapshot_file}.[/dim]"
            )

    # --- shared rendering --------------------------------------------------

    def _print_skipped(self, skipped: List[Tuple[str, str]], noun: str) -> None:
        if not skipped:
            return
        console.print(f"\n[yellow]Skipped {len(skipped)} {noun}(s):[/yellow]")
        for path, reason in skipped[:20]:
            console.print(f"  [yellow]{reason}[/yellow] — {path}")
        if len(skipped) > 20:
            console.print(f"  [dim]… +{len(skipped) - 20} more[/dim]")
