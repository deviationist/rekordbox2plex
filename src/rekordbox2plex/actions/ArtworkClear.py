import os
from typing import Any, Dict, List

from rich.table import Table

from ._ActionBase import ActionBase
from ..config import (
    get_clear_kinds,
    get_only_rating_keys,
    get_plex_container_name,
    get_plex_db_path,
    get_plex_docker_image,
    get_plex_metadata_path,
    get_plex_sqlite_bin,
    get_plex_sqlite_mechanism,
    should_allow_running,
    should_keep_files,
    should_write,
)
from ..plex.PlexDBReader import read_upload_posters
from ..plex.PlexDBWriter import (
    apply_plan_docker,
    apply_plan_sqlite3,
    build_clear_posters_sql,
    container_state,
    count_updates,
)
from ..plex.poster_files import (
    delete_poster_files_docker,
    metadata_dir_from_db_path,
    poster_file_path,
)
from ..plex.resolvers.library import get_music_library_name
from ..utils.confirm import confirm_destructive
from ..utils.logger import console, logger

_KIND = {8: "artist", 9: "album"}


class ArtworkClear(ActionBase):
    """Remove uploaded **artist/album posters** from a Plex library — both the DB
    selection AND the on-disk image file.

    Clears ``metadata_items.user_thumb_url`` (what selects the poster) via a direct
    Plex DB write — the only way to delete an uploaded poster, since the HTTP API
    can't — and then deletes the uploaded image file from the item's metadata
    bundle (``…/<bundle>/Uploads/posters/``), which Plex's Clean Bundles/Optimize
    do NOT remove. Pass ``--keep-files`` to clear the DB selection only.

    Targets only items whose poster is an ``upload://`` image (one set by a tool or
    manually) — never embedded APIC art or an agent thumb. Scope is chosen with
    ``--kind`` (artist / album / both) and optionally narrowed to ``--only
    <ratingKeys>``. Read-only by default (lists what would change); ``--write``
    requires Plex stopped + the ``CLEAR-IMAGES`` token and uses the same bundled
    "Plex SQLite" + docker-as-owner mechanism as the ``dates`` write.

    Use it to reset before repopulating with ``artist-images`` — e.g. after
    improving the matcher — so stale/wrong posters don't linger."""

    def __init__(self) -> None:
        super().__init__("clear artwork")
        self.plex_db_path = get_plex_db_path()
        self.kinds = get_clear_kinds()
        self.keep_files = should_keep_files()
        self.metadata_dir = None
        if self.plex_db_path:
            self.metadata_dir = get_plex_metadata_path() or metadata_dir_from_db_path(
                self.plex_db_path
            )

    def run(self) -> None:
        if not self.plex_db_path:
            logger.error("[red]PLEX_DB_PATH is not set — clear-art needs it.")
            return
        if should_write():
            self.apply()
        else:
            self.preview()

    # --- shared --------------------------------------------------------------

    def _targets(self) -> List[Dict[str, Any]]:
        assert self.plex_db_path is not None
        rows = read_upload_posters(
            self.plex_db_path, get_music_library_name(), self.kinds
        )
        only = get_only_rating_keys()
        if only:
            rows = [r for r in rows if int(r["id"]) in only]
        # Resolve each poster's on-disk file and whether it currently exists.
        for r in rows:
            path = (
                poster_file_path(
                    self.metadata_dir,
                    r["metadata_type"],
                    r.get("guid") or "",
                    r["user_thumb_url"],
                )
                if self.metadata_dir
                else None
            )
            r["file"] = path
            r["file_exists"] = bool(path and os.path.isfile(path))
        return rows

    def _scope_label(self) -> str:
        return "+".join(_KIND.get(t, str(t)) for t in self.kinds)

    def _album_note(self) -> None:
        """Albums almost always have an embedded cover, so clearing the selected
        upload reverts to that — but warn, since it's the user's art."""
        if 9 in self.kinds:
            console.print(
                "[yellow]Note: album posters normally have an embedded cover behind "
                "them, so clearing reverts to the embedded art (not blank). Artists "
                "have no embedded source, so they blank out. Test one with --only "
                "first if unsure.[/yellow]"
            )

    def _table(self, rows: List[Dict[str, Any]]) -> None:
        shown = rows[:30]
        table = Table(title=f"Posters to clear (showing {len(shown)} of {len(rows)})")
        table.add_column("ratingKey", justify="right", style="dim")
        table.add_column("Kind", style="cyan")
        table.add_column("Title")
        table.add_column("File", justify="center")
        table.add_column("Current poster", style="dim", overflow="fold")
        for r in shown:
            if self.keep_files:
                fcol = "[dim]kept[/dim]"
            elif r["file_exists"]:
                fcol = "[red]delete[/red]"
            else:
                fcol = "[dim]missing[/dim]"
            table.add_row(
                str(r["id"]),
                _KIND.get(r["metadata_type"], str(r["metadata_type"])),
                r["title"],
                fcol,
                r["user_thumb_url"],
            )
        console.print(table)

    def _file_summary(self, rows: List[Dict[str, Any]]) -> int:
        return sum(1 for r in rows if r["file_exists"])

    # --- dry run -------------------------------------------------------------

    def preview(self) -> None:
        only = get_only_rating_keys()
        scope = f" only={sorted(only)}" if only else " (all uploaded posters)"
        files = "keep files (DB only)" if self.keep_files else "delete files too"
        console.print(
            f"[bold cyan]Dry run (read-only)[/bold cyan]  kind: "
            f"{self._scope_label()}{scope}  |  {files}\n"
        )
        rows = self._targets()
        if not rows:
            console.print("[bold green]✔ No uploaded posters to clear.")
            return
        self._table(rows)
        console.print(f"\n[bold]Posters that would be cleared:[/bold] {len(rows)}")
        if not self.keep_files:
            console.print(
                f"[bold]Image files that would be deleted:[/bold] "
                f"{self._file_summary(rows)}"
            )
        self._album_note()
        console.print(
            "\n[dim]Dry run — nothing modified. "
            "Re-run with --write (Plex stopped) to apply.[/dim]"
        )

    # --- write ---------------------------------------------------------------

    def _guard_stopped(self) -> bool:
        """Mirror the dates write guard: never stop Plex ourselves."""
        container = get_plex_container_name()
        state = container_state(container)
        if state == "running" and not should_allow_running():
            logger.error(
                f"[red]Refusing to write: container '{container}' is running. "
                f"Stop the Plex container first (e.g. `docker compose down` in your "
                f"Plex stack directory), then re-run.[/red]\n"
                f"[dim](or pass --allow-running only when targeting a scratch copy)[/dim]"
            )
            return False
        if state == "running" and should_allow_running():
            console.print(
                f"[bold red]⚠ Container '{container}' is RUNNING but --allow-running "
                f"was passed (scratch-copy mode). Proceeding.[/bold red]"
            )
        elif state is None:
            console.print(
                f"[yellow]Could not verify container '{container}' state — "
                f"ensure Plex is stopped.[/yellow]"
            )
        return True

    def apply(self) -> None:
        assert self.plex_db_path is not None
        rows = self._targets()
        n = len(rows)
        if n == 0:
            logger.info("[green]Nothing to clear — no uploaded posters found.")
            return
        if not self._guard_stopped():
            return

        self._table(rows)
        self._album_note()
        nfiles = 0 if self.keep_files else self._file_summary(rows)
        console.print(
            f"\n[bold]About to clear [red]{n}[/red] poster(s)[/bold] "
            f"({self._scope_label()}; user_thumb_url='')"
            + (
                f" and delete [red]{nfiles}[/red] image file(s)"
                if not self.keep_files
                else " (keeping files)"
            )
            + f" in:\n  {self.plex_db_path}"
        )
        console.print(
            "[yellow]Prerequisite (manual, not automated): back up this DB plus its "
            "-wal/-shm siblings with Plex stopped before proceeding.[/yellow]"
        )
        if not confirm_destructive(
            f"This will clear the uploaded poster on {n} Plex item(s) "
            f"({self._scope_label()}; "
            + ("DB only" if self.keep_files else f"+ delete {nfiles} files")
            + ") — no other metadata touched.",
            "CLEAR-IMAGES",
            title="Clear Artwork",
        ):
            logger.info("[yellow]Aborted — confirmation token did not match.")
            return

        # 1) Clear the DB selection.
        sql = build_clear_posters_sql([r["id"] for r in rows])
        mechanism = get_plex_sqlite_mechanism()
        if mechanism == "sqlite3":
            apply_plan_sqlite3(self.plex_db_path, sql)
            console.print(
                f"[bold green]✔ Cleared {n} poster(s) via stock sqlite3.[/bold green]"
            )
        else:
            proc = apply_plan_docker(
                self.plex_db_path, sql, get_plex_docker_image(), get_plex_sqlite_bin()
            )
            if proc.returncode != 0:
                logger.error(
                    f"[red]Plex SQLite write failed (exit {proc.returncode}):[/red]\n"
                    f"{proc.stderr}"
                )
                return
            console.print(
                f"[bold green]✔ Cleared {count_updates(sql)} poster(s) "
                f"via bundled Plex SQLite.[/bold green]"
            )
            if proc.stdout.strip():
                console.print(f"[dim]{proc.stdout.strip()}[/dim]")

        # 2) Delete the on-disk image files (unless --keep-files).
        if not self.keep_files:
            self._delete_files(rows)
        console.print(
            "[dim]Start Plex, then repopulate with `artist-images --write`.[/dim]"
        )

    def _delete_files(self, rows: List[Dict[str, Any]]) -> None:
        assert self.metadata_dir is not None
        paths = [r["file"] for r in rows if r["file_exists"]]
        if not paths:
            console.print("[dim]No on-disk poster files to delete.[/dim]")
            return
        proc = delete_poster_files_docker(
            self.metadata_dir, paths, get_plex_docker_image()
        )
        if proc is not None and proc.returncode != 0:
            logger.error(
                f"[red]File deletion failed (exit {proc.returncode}):[/red]\n"
                f"{proc.stderr}"
            )
            return
        remaining = sum(1 for p in paths if os.path.isfile(p))
        deleted = len(paths) - remaining
        console.print(
            f"[bold green]✔ Deleted {deleted}/{len(paths)} image file(s) "
            f"from the Plex bundles.[/bold green]"
        )
        if remaining:
            console.print(f"[yellow]{remaining} file(s) still present.[/yellow]")
