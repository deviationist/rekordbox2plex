import os
from typing import Dict, List, Optional, Set, Tuple

from rich.table import Table

from ._ActionBase import ActionBase
from ..config import (
    get_aiff_backup_dir,
    get_only_rating_keys,
    get_plex_db_path,
    get_plex_media_path_map,
    should_refresh_plex,
    should_remove_name,
    should_write,
)
from ..plex.PlexDBReader import read_tracks_metadata
from ..plex.resolvers.library import get_music_library_name
from ..utils.aiff_chunks import read_id3_title, read_name, rewrite_name
from ..utils.confirm import confirm_destructive
from ..utils.logger import console, logger
from ..utils.media_paths import parse_media_path_map, resolve_host_path
from ..utils.paths import PROJECT_ROOT
from ..utils.progress_bar import progress_instance

AIFF_EXTS = (".aiff", ".aif")


def _fmt(value: Optional[str]) -> str:
    if value is None or value == "":
        return "[dim]—[/dim]"
    return value


class AiffTitleFix(ActionBase):
    """Repair AIFF titles where the legacy native ``NAME`` chunk (which Plex
    reads) shadows the correct ID3 ``TIT2`` (which Rekordbox/OneTagger use).

    Read-only by default: prints the ``NAME → ID3 title`` diff as a table.
    ``--write`` rewrites the ``NAME`` chunk (set to TIT2, or removed with
    ``--remove-name``) behind a typed confirmation, backing up each original."""

    def __init__(self) -> None:
        super().__init__("aiff title fix")
        self.plex_db_path = get_plex_db_path()
        self.path_map = parse_media_path_map(get_plex_media_path_map())
        self.remove_name = should_remove_name()
        self.refresh = should_refresh_plex()

    def run(self) -> None:
        if not self.plex_db_path:
            logger.error(
                "[red]PLEX_DB_PATH is not set — the aiff-titles command needs it."
            )
            return
        if not self.path_map:
            logger.error(
                "[red]PLEX_MEDIA_PATH_MAP is not set — it's required to locate the "
                "audio files on disk (e.g. PLEX_MEDIA_PATH_MAP=/data/music=/tank/music)."
            )
            return
        if should_write():
            self.apply()
        else:
            self.preview()

    # --- diff computation --------------------------------------------------

    def compute(
        self, filter_ids: Optional[Set[int]] = None
    ) -> Tuple[List[Dict], List[Tuple[Dict, str]]]:
        """Return (diffs, skipped). Each diff: {rk, host, plex_path, current
        (NAME), target (TIT2)}. skipped: (track, reason) for files we couldn't
        inspect (no host mapping / missing on disk / no ID3 title)."""
        assert self.plex_db_path is not None  # guaranteed by run()
        tracks = read_tracks_metadata(self.plex_db_path, get_music_library_name())
        if filter_ids is not None:
            tracks = [t for t in tracks if t["rk"] in filter_ids]
        aiff = [
            t for t in tracks if t["file"] and t["file"].lower().endswith(AIFF_EXTS)
        ]

        diffs: List[Dict] = []
        skipped: List[Tuple[Dict, str]] = []
        with progress_instance() as progress:
            task = progress.add_task("", total=len(aiff))
            for t in aiff:
                progress.update(
                    task, advance=1, description=f'[cyan]Inspecting "{t["title"]}"...'
                )
                host = resolve_host_path(t["file"], self.path_map)
                if host is None:
                    skipped.append((t, "no PLEX_MEDIA_PATH_MAP prefix"))
                    continue
                if not os.path.isfile(host):
                    skipped.append((t, "file not found on host"))
                    continue
                name = read_name(host)
                if name is None:
                    continue  # no NAME chunk → Plex already uses ID3; nothing to fix
                tit2 = read_id3_title(host)
                if tit2 is None:
                    skipped.append((t, "no ID3 TIT2 in file"))
                    continue
                if name != tit2:
                    diffs.append(
                        {
                            "rk": t["rk"],
                            "host": host,
                            "plex_path": t["file"],
                            "current": name,
                            "target": tit2,
                        }
                    )
        return diffs, skipped

    # --- rendering ---------------------------------------------------------

    def _print_table(self, diffs: List[Dict]) -> None:
        action = "remove → fall back to ID3" if self.remove_name else "set to ID3 title"
        table = Table(title=f"AIFF NAME-chunk title diff ({action})")
        table.add_column("#", justify="right", style="dim")
        table.add_column("ratingKey", justify="right", style="dim")
        table.add_column("Plex shows (NAME)", style="cyan")
        table.add_column("ID3 title (TIT2)", style="green")
        table.add_column("File", style="dim", overflow="fold")
        for i, d in enumerate(diffs, 1):
            table.add_row(
                str(i),
                str(d["rk"]),
                _fmt(d["current"]),
                _fmt(d["target"]),
                _fmt(d["host"]),
            )
        console.print(table)

    def _print_skipped(self, skipped: List[Tuple[Dict, str]]) -> None:
        if not skipped:
            return
        console.print(f"\n[yellow]Skipped {len(skipped)} AIFF file(s):[/yellow]")
        for t, reason in skipped[:20]:
            console.print(f"  [yellow]{reason}[/yellow] — {t['file']} (id {t['rk']})")
        if len(skipped) > 20:
            console.print(f"  [dim]… +{len(skipped) - 20} more[/dim]")

    # --- dry run -----------------------------------------------------------

    def preview(self) -> None:
        only = get_only_rating_keys()
        scope = f" only={sorted(only)}" if only else ""
        console.print(f"[bold cyan]Dry run (read-only)[/bold cyan]{scope}\n")
        diffs, skipped = self.compute(only)
        if diffs:
            self._print_table(diffs)
        console.print(f"\n[bold]AIFF titles needing repair:[/bold] {len(diffs)}")
        self._print_skipped(skipped)
        if diffs:
            console.print(
                "\n[dim]Dry run — no files modified. Re-run with --write to apply.[/dim]"
            )
        else:
            console.print("[bold green]✔ No AIFF NAME-chunk title mismatches found.")

    # --- write -------------------------------------------------------------

    def _backup_dir(self) -> str:
        return get_aiff_backup_dir() or str(PROJECT_ROOT / "aiff-title-backups")

    def apply(self) -> None:
        diffs, skipped = self.compute(get_only_rating_keys())
        self._print_skipped(skipped)
        n = len(diffs)
        if n == 0:
            logger.info(
                "[green]Nothing to change — no AIFF NAME-chunk title mismatches."
            )
            return

        self._print_table(diffs)
        backup_dir = self._backup_dir()
        action = (
            "remove the NAME chunk from"
            if self.remove_name
            else "set the NAME chunk to the ID3 title on"
        )
        console.print(
            f"\n[bold]About to {action} [red]{n}[/red] AIFF file(s).[/bold]\n"
            f"  Originals are backed up under: {backup_dir}"
        )
        if not confirm_destructive(
            f"This will {action} {n} AIFF file(s) (audio + ID3 left untouched).",
            "WRITE-TITLES",
            title="Write AIFF Titles",
        ):
            logger.info("[yellow]Aborted — confirmation token did not match.")
            return

        ok = 0
        failed: List[Tuple[Dict, str]] = []
        with progress_instance() as progress:
            task = progress.add_task("", total=n)
            for d in diffs:
                progress.update(
                    task, advance=1, description=f'[cyan]Writing "{d["target"]}"...'
                )
                new_value = None if self.remove_name else d["target"]
                try:
                    rewrite_name(d["host"], new_value, backup_dir)
                    ok += 1
                except Exception as e:  # noqa: BLE001 - report and continue
                    failed.append((d, str(e)))
        console.print(f"[bold green]✔ Rewrote {ok}/{n} AIFF file(s).[/bold green]")
        for d, err in failed:
            logger.error(f"[red]Failed: {d['host']}: {err}")

        if ok:
            self._after_write([d for d in diffs if d not in [f[0] for f in failed]])

    def _after_write(self, written: List[Dict]) -> None:
        if self.refresh:
            self._refresh_albums(written)
        else:
            console.print(
                "\n[dim]Plex still shows the old titles until it re-reads the files. "
                "In Plex, run album-level 'Refresh Metadata' on the affected albums, "
                "or re-run with --refresh-plex to do it automatically.[/dim]"
            )

    def _refresh_albums(self, written: List[Dict]) -> None:
        from ..plex.PlexClient import plexapi_client

        server = plexapi_client()
        albums: Dict[int, str] = {}
        for d in written:
            try:
                track = server.fetchItem(int(d["rk"]))
                ak = getattr(track, "parentRatingKey", None)
                if ak is not None:
                    albums[int(ak)] = getattr(track, "parentTitle", "?")
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"[yellow]Could not resolve album for ratingKey {d['rk']}: {e}"
                )
        if not albums:
            logger.warning("[yellow]No albums resolved to refresh.")
            return
        console.print(f"\n[cyan]Refreshing {len(albums)} album(s) in Plex…[/cyan]")
        for ak, title in albums.items():
            try:
                server.fetchItem(ak).refresh()
                console.print(f"  [green]refreshed[/green] {title} (album {ak})")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[yellow]Refresh failed for album {ak}: {e}")
