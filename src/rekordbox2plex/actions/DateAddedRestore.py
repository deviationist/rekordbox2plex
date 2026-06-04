from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from rich.table import Table

from ._ActionBase import ActionBase
from ..config import (
    get_plan_file,
    get_plex_container_name,
    get_plex_db_path,
    get_plex_docker_image,
    get_plex_sqlite_bin,
    get_plex_sqlite_mechanism,
    get_only_rating_keys,
    get_rb_added_at_field,
    get_validate_album,
    get_validate_track,
    should_allow_running,
    should_include_albums,
    should_include_tracks,
    should_write,
)
from ..plex.PlexDBReader import read_library
from ..plex.PlexDBWriter import (
    apply_plan_docker,
    apply_plan_sqlite3,
    build_plan_sql,
    container_state,
    count_updates,
)
from ..plex.resolvers.library import get_music_library_name
from ..rekordbox.resolvers.added_at import (
    RB_TIMESTAMP_FIELDS,
    get_rb_timestamps,
    parse_rb_timestamp,
    resolve_rb_added_at,
    rollup_added_at,
    to_epoch,
)
from ..rekordbox.resolvers.track import (
    convert_path_to_rekordbox,
    resolve_track_id_by_plex_path,
)
from ..utils.confirm import confirm_destructive
from ..utils.logger import console, logger
from ..utils.progress_bar import progress_instance


def _fmt_epoch(epoch: Optional[int]) -> str:
    if epoch is None:
        return "[dim]—[/dim]"
    return f"{epoch} ({datetime.fromtimestamp(epoch, timezone.utc):%Y-%m-%d %H:%M:%S} UTC)"


class Plan:
    """The computed set of changes, held entirely in memory (no file)."""

    def __init__(self) -> None:
        self.tracks_total = 0
        self.matched = 0
        self.unmatched: List[str] = []
        self.no_timestamp: List[str] = []
        self.collisions: List[str] = []
        self.track_updates: List[Dict] = []
        self.album_updates: List[Dict] = []


class DateAddedRestore(ActionBase):
    def __init__(self) -> None:
        super().__init__("date added sync")
        self.field = get_rb_added_at_field()
        self.plex_db_path = get_plex_db_path()
        self.include_tracks = should_include_tracks()
        self.include_albums = should_include_albums()

    def run(self) -> None:
        if not self.plex_db_path:
            logger.error("[red]PLEX_DB_PATH is not set — the dates command needs it.")
            return

        validate_track = get_validate_track()
        validate_album = get_validate_album()
        if validate_track or validate_album:
            console.print(
                "[bold cyan]Single-item validation (read-only, no writes)[/bold cyan]\n"
            )
            if validate_track:
                self.validate(int(validate_track), is_album=False)
            if validate_album:
                self.validate(int(validate_album), is_album=True)
            return

        if should_write():
            self.apply()
        else:
            self.preview()

    # --- plan computation --------------------------------------------------

    def compute_plan(self, filter_ids: Optional[Set[int]] = None) -> Plan:
        assert self.plex_db_path is not None  # guaranteed by run()
        _, tracks, albums = read_library(self.plex_db_path, get_music_library_name())
        if filter_ids is not None:
            tracks = [
                t
                for t in tracks
                if t["rk"] in filter_ids or t["album_id"] in filter_ids
            ]

        plan = Plan()
        plan.tracks_total = len(tracks)
        rb_owner: Dict[int, int] = {}
        album_props: Dict[int, List[int]] = {}

        with progress_instance() as progress:
            task = progress.add_task("", total=len(tracks))
            for t in tracks:
                progress.update(task, description=f'[cyan]Resolving "{t["title"]}"...')
                rb_id = resolve_track_id_by_plex_path(t["file"]) if t["file"] else None
                if rb_id is None:
                    plan.unmatched.append(t["file"] or f"(no file) id={t['rk']}")
                    progress.update(task, advance=1)
                    continue
                plan.matched += 1
                if rb_id in rb_owner:
                    plan.collisions.append(
                        f"rb_id {rb_id}: ids {rb_owner[rb_id]} & {t['rk']}"
                    )
                else:
                    rb_owner[rb_id] = t["rk"]

                proposed = resolve_rb_added_at(rb_id)
                if proposed is None:
                    plan.no_timestamp.append(f"{t['title']} (rb_id {rb_id})")
                    progress.update(task, advance=1)
                    continue

                # Every matched track feeds its album's rollup (so a targeted
                # album still gets the true min across ALL its tracks)...
                album_props.setdefault(t["album_id"], []).append(proposed)
                # ...but only emit a track UPDATE when that track id is targeted.
                track_targeted = filter_ids is None or t["rk"] in filter_ids
                if track_targeted and proposed != t["added_at"]:
                    plan.track_updates.append(
                        {
                            "id": t["rk"],
                            "proposed": proposed,
                            "current": t["added_at"],
                            "title": t["title"],
                        }
                    )
                progress.update(task, advance=1)

        for album_id, epochs in album_props.items():
            if filter_ids is not None and album_id not in filter_ids:
                continue  # album not targeted (its tracks were pulled in only for rollup context)
            proposed = rollup_added_at(epochs)
            if proposed is None:
                continue
            current = albums.get(album_id, {}).get("added_at")
            if proposed != current:
                plan.album_updates.append(
                    {
                        "id": album_id,
                        "proposed": proposed,
                        "current": current,
                        "title": albums.get(album_id, {}).get("title", "?"),
                    }
                )
        return plan

    def _scoped(self, plan: Plan):
        tracks = plan.track_updates if self.include_tracks else []
        albums = plan.album_updates if self.include_albums else []
        return tracks, albums

    # --- dry-run -----------------------------------------------------------

    def preview(self) -> None:
        only = get_only_rating_keys()
        scope = f" only={sorted(only)}" if only else ""
        console.print(
            f"[bold cyan]Dry run (read-only)[/bold cyan]  "
            f"tracks={self.include_tracks} albums={self.include_albums}{scope}\n"
        )
        plan = self.compute_plan(only)
        tracks, albums = self._scoped(plan)
        self._print_summary(plan, tracks, albums)
        self._print_samples(tracks, albums)
        self._maybe_dump(tracks, albums)
        console.print(
            "\n[dim]Dry run — no database was modified. "
            "Re-run with --write (Plex stopped) to apply.[/dim]"
        )

    def _print_summary(self, plan: Plan, tracks, albums) -> None:
        table = Table(title="Date-added plan summary")
        table.add_column("metric")
        table.add_column("count", justify="right")
        table.add_row("Plex tracks", str(plan.tracks_total))
        table.add_row("matched to Rekordbox", str(plan.matched))
        table.add_row("unmatched", str(len(plan.unmatched)))
        table.add_row("matched but no rb timestamp", str(len(plan.no_timestamp)))
        table.add_row("rb_id collisions", str(len(plan.collisions)))
        table.add_row("[bold]track changes", f"[bold]{len(tracks)}")
        table.add_row("[bold]album changes", f"[bold]{len(albums)}")
        console.print(table)
        for label, items in (
            ("collisions", plan.collisions),
            ("matched but missing rb timestamp", plan.no_timestamp),
        ):
            if items:
                console.print(f"[yellow]{label}:[/yellow]")
                for x in items[:20]:
                    console.print(f"  [yellow]{x}[/yellow]")
                if len(items) > 20:
                    console.print(f"  [dim]… +{len(items) - 20} more[/dim]")

    def _print_samples(self, tracks, albums) -> None:
        for kind, rows in (("track", tracks), ("album", albums)):
            if not rows:
                continue
            shown = rows[:25]
            table = Table(title=f"{kind} changes (showing {len(shown)} of {len(rows)})")
            table.add_column("id")
            table.add_column("title")
            table.add_column("current → proposed")
            for u in shown:
                table.add_row(
                    str(u["id"]),
                    str(u["title"]),
                    f"{_fmt_epoch(u['current'])} → {_fmt_epoch(u['proposed'])}",
                )
            console.print(table)

    def _maybe_dump(self, tracks, albums) -> None:
        path = get_plan_file()
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(build_plan_sql(tracks, albums))
        console.print(f"[dim]Wrote SQL plan to {path} (for inspection).[/dim]")

    # --- write -------------------------------------------------------------

    def apply(self) -> None:
        assert self.plex_db_path is not None  # guaranteed by run()
        plan = self.compute_plan(get_only_rating_keys())
        tracks, albums = self._scoped(plan)
        n = len(tracks) + len(albums)
        if n == 0:
            logger.info("[green]Nothing to change — Plex already matches Rekordbox.")
            return

        # Constraint 3: verify Plex is stopped (never stop it ourselves).
        container = get_plex_container_name()
        state = container_state(container)
        if state == "running" and not should_allow_running():
            logger.error(
                f"[red]Refusing to write: container '{container}' is running. "
                f"Stop it first:[/red]\n"
                f"  cd /home/xavi/docker-root/plex && docker compose down\n"
                f"[dim](or pass --allow-running only when targeting a scratch copy)[/dim]"
            )
            return
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

        self._print_summary(plan, tracks, albums)
        self._print_samples(tracks, albums)
        sql = build_plan_sql(tracks, albums)
        self._maybe_dump(tracks, albums)

        mechanism = get_plex_sqlite_mechanism()
        console.print(
            f"\n[bold]About to write [red]{n}[/red] rows[/bold] to:\n  "
            f"{self.plex_db_path}\n  mechanism: {mechanism}"
        )
        console.print(
            "[yellow]Prerequisite (manual, not automated): back up this DB plus its "
            "-wal/-shm siblings with Plex stopped before proceeding.[/yellow]"
        )
        if not confirm_destructive(
            f"This will overwrite added_at on {n} metadata_items rows in the Plex DB.",
            "WRITE-DATES",
            title="Write Date Added",
        ):
            logger.info("[yellow]Aborted — confirmation token did not match.")
            return

        if mechanism == "sqlite3":
            apply_plan_sqlite3(self.plex_db_path, sql)
            console.print(f"[bold green]✔ Applied {n} UPDATEs via stock sqlite3.[/bold green]")
            return

        proc = apply_plan_docker(
            self.plex_db_path, sql, get_plex_docker_image(), get_plex_sqlite_bin()
        )
        if proc.returncode != 0:
            logger.error(
                f"[red]Plex SQLite write failed (exit {proc.returncode}):[/red]\n{proc.stderr}"
            )
            return
        console.print(
            f"[bold green]✔ Applied {count_updates(sql)} UPDATEs via bundled Plex SQLite.[/bold green]"
        )
        if proc.stdout.strip():
            console.print(f"[dim]{proc.stdout.strip()}[/dim]")

    # --- single-item validation -------------------------------------------

    def validate(self, rating_key: int, is_album: bool) -> None:
        assert self.plex_db_path is not None  # guaranteed by run()
        _, tracks, albums = read_library(self.plex_db_path, get_music_library_name())

        if not is_album:
            row = next((t for t in tracks if t["rk"] == rating_key), None)
            if row is None:
                logger.error(f"[red]No track with id {rating_key} in the music library.")
                return
            console.rule(f"[bold]TRACK  {row['title']} — id {rating_key}")
            console.print(f"file_path      : {row['file']}")
            console.print(f"rekordbox path : {convert_path_to_rekordbox(row['file'])}")
            console.print(f"current added_at: {_fmt_epoch(row['added_at'])}")
            rb_id = resolve_track_id_by_plex_path(row["file"])
            if rb_id is None:
                logger.warning("[yellow]No Rekordbox match for this file.")
                return
            self._timestamp_table(rb_id)
            proposed = resolve_rb_added_at(rb_id)
            console.print(f"\n[bold]Proposed[/bold] ({self.field}): {_fmt_epoch(proposed)}")
            console.print(
                f"[bold yellow]WOULD RUN (no write):[/bold yellow] "
                f"UPDATE metadata_items SET added_at = {proposed} WHERE id = {rating_key};\n"
            )
            return

        info = albums.get(rating_key)
        if info is None:
            logger.error(f"[red]No album with id {rating_key} in the music library.")
            return
        console.rule(f"[bold]ALBUM  {info['title']} — id {rating_key}")
        console.print(f"current added_at: {_fmt_epoch(info['added_at'])}")
        proposals: List[int] = []
        table = Table(title="Album tracks → proposed")
        table.add_column("id")
        table.add_column("title")
        table.add_column("rb_id")
        table.add_column("proposed")
        for t in [t for t in tracks if t["album_id"] == rating_key]:
            rb_id = resolve_track_id_by_plex_path(t["file"]) if t["file"] else None
            proposed = resolve_rb_added_at(rb_id) if rb_id is not None else None
            if proposed is not None:
                proposals.append(proposed)
            table.add_row(
                str(t["rk"]),
                t["title"],
                str(rb_id) if rb_id is not None else "[red]none[/red]",
                _fmt_epoch(proposed),
            )
        console.print(table)
        album_proposed = rollup_added_at(proposals)
        console.print(
            f"\n[bold]Album rollup[/bold] = min(track proposals) = {_fmt_epoch(album_proposed)}"
        )
        console.print(
            f"[bold yellow]WOULD RUN (no write):[/bold yellow] "
            f"UPDATE metadata_items SET added_at = {album_proposed} WHERE id = {rating_key};\n"
        )

    def _timestamp_table(self, rb_id: int) -> None:
        raw = get_rb_timestamps(rb_id)
        table = Table(title=f"Rekordbox djmdContent timestamps (ID={rb_id})")
        table.add_column("field")
        table.add_column("raw")
        table.add_column("→ UTC epoch")
        for field in RB_TIMESTAMP_FIELDS:
            epoch = to_epoch(parse_rb_timestamp(raw.get(field)))
            marker = " [bold green](chosen)[/bold green]" if field == self.field else ""
            table.add_row(f"{field}{marker}", str(raw.get(field)), _fmt_epoch(epoch))
        console.print(table)
