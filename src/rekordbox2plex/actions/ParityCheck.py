import json
from typing import Dict, List, Optional, Set

from rich.table import Table

from ._ActionBase import ActionBase
from ..artwork.collab import split_collab
from ..config import (
    get_collab_ambiguous_separators,
    get_collab_primary_separators,
    get_only_rating_keys,
    get_orphan_limit,
    get_parity_fields,
    get_plex_db_path,
    get_rb_folder_paths_to_ignore,
    should_include_orphans,
    should_match_artist_order,
    should_output_json,
    should_split_artists,
)
from ..plex.PlexDBReader import read_tracks_metadata
from ..plex.resolvers.library import get_music_library_name
from ..rekordbox.resolvers.metadata import get_all_rb_track_ids, get_rb_metadata
from ..rekordbox.resolvers.track import (
    convert_path_to_rekordbox,
    is_ignored_rb_path,
    resolve_track_id_by_rb_path,
)
from ..utils.logger import console, logger
from ..utils.normalize import normalize
from ..utils.progress_bar import progress_instance

# Display labels for each comparable field, in stable report order.
FIELD_LABELS = {
    "title": "Title",
    "artist": "Artist",
    "album": "Album",
    "albumartist": "AlbumArtist",
}

# Artist-name fields eligible for the --split-artists set-comparison fallback.
ARTIST_FIELDS = ("artist", "albumartist")


def _fmt(value: Optional[str]) -> str:
    if value is None or value == "":
        return "[dim]—[/dim]"
    return value


class ParityReport:
    """Outcome of a parity scan, held entirely in memory (read-only command)."""

    def __init__(self) -> None:
        self.scanned = 0  # total Plex tracks walked (= compared + unmatched + ignored)
        self.compared = 0
        self.ignored = 0  # tracks skipped via REKORDBOX_FOLDER_PATHS_TO_IGNORE
        # each: {rk, field, plex, rb, label}
        self.mismatches: List[Dict] = []
        # Plex tracks with no Rekordbox match: {rk, title, file}
        self.plex_orphans: List[Dict] = []
        # Rekordbox collection ids with no Plex match (full set; sampled on print)
        self.rb_orphan_ids: List[int] = []
        self.matched_rb_ids: Set[int] = set()


class ParityCheck(ActionBase):
    def __init__(self) -> None:
        self.as_json = should_output_json()
        super().__init__("parity check", quiet=self.as_json)
        self.plex_db_path = get_plex_db_path()
        self.fields = get_parity_fields()
        self.include_orphans = should_include_orphans()
        self.orphan_limit = get_orphan_limit()
        self.ignore_paths = get_rb_folder_paths_to_ignore()
        # --split-artists: decompose artist strings and compare the component
        # set on a direct miss. Separators reuse the artist-images collab config
        # (primary always-on + the opt-in ambiguous tier, e.g. & / +).
        self.split_artists = should_split_artists()
        self.match_artist_order = should_match_artist_order()
        self.artist_separators = (
            get_collab_primary_separators() + get_collab_ambiguous_separators()
        )

    def run(self) -> None:
        if not self.plex_db_path:
            logger.error("[red]PLEX_DB_PATH is not set — the parity command needs it.")
            return
        report = self.compute_report(get_only_rating_keys())
        self._render(report)

    # --- report computation (pure-ish; deps are monkeypatchable in tests) ---

    def compute_report(self, filter_ids: Optional[Set[int]] = None) -> ParityReport:
        assert self.plex_db_path is not None  # guaranteed by run()
        tracks = read_tracks_metadata(self.plex_db_path, get_music_library_name())
        if filter_ids is not None:
            tracks = [t for t in tracks if t["rk"] in filter_ids]

        report = ParityReport()
        report.scanned = len(tracks)
        with progress_instance(enabled=not self.as_json) as progress:
            task = progress.add_task("", total=len(tracks))
            for t in tracks:
                progress.update(
                    task,
                    advance=1,
                    description=(
                        f'[cyan]Checking "{t["title"]}" '
                        f"[dim](mapped {report.compared}, "
                        f"unmatched {len(report.plex_orphans)})"
                    ),
                )
                rb_path = convert_path_to_rekordbox(t["file"]) if t["file"] else None
                if is_ignored_rb_path(rb_path, self.ignore_paths):
                    report.ignored += 1
                    continue

                rb_id = resolve_track_id_by_rb_path(rb_path) if rb_path else None
                rb = get_rb_metadata(rb_id) if rb_id is not None else None
                if rb_id is None or rb is None:
                    report.plex_orphans.append(
                        {"rk": t["rk"], "title": t["title"], "file": t["file"]}
                    )
                    continue

                report.matched_rb_ids.add(rb_id)
                report.compared += 1
                self._compare(t, rb, report)

        # Rekordbox-side orphans only make sense over a full (unfiltered) scan.
        if self.include_orphans and filter_ids is None:
            report.rb_orphan_ids = sorted(
                get_all_rb_track_ids(self.ignore_paths) - report.matched_rb_ids
            )
        return report

    def _compare(self, t: Dict, rb: Dict, report: ParityReport) -> None:
        # Plex stores the per-track artist in original_title, leaving it empty
        # when it equals the album artist — fall back so we compare like for like.
        plex_track_artist = t["track_artist"] or t["album_artist"]
        plex_vals = {
            "title": t["title"],
            "artist": plex_track_artist,
            "album": t["album"],
            "albumartist": t["album_artist"],
        }
        rb_vals = {
            "title": rb["title"],
            "artist": rb["artist"],
            "album": rb["album"],
            "albumartist": rb["album_artist"],
        }
        label = f'{t["title"]} — {plex_track_artist or "?"}'
        for field in FIELD_LABELS:
            if field not in self.fields:
                continue
            if normalize(plex_vals[field]) == normalize(rb_vals[field]):
                continue
            if (
                self.split_artists
                and field in ARTIST_FIELDS
                and self._artists_equivalent(plex_vals[field], rb_vals[field])
            ):
                continue
            report.mismatches.append(
                {
                    "rk": t["rk"],
                    "field": field,
                    "plex": plex_vals[field],
                    "rb": rb_vals[field],
                    "label": label,
                    "file": t["file"],
                }
            )

    def _artist_components(self, value: Optional[str]) -> List[str]:
        """Decompose an artist string into normalized component names using the
        shared collab separators. A value that doesn't split yields its single
        normalized self; empty components are dropped."""
        parts = split_collab(value or "", self.artist_separators) or [value or ""]
        return [n for n in (normalize(p) for p in parts) if n]

    def _artists_equivalent(self, plex: Optional[str], rb: Optional[str]) -> bool:
        """True if both artist strings decompose to the same component artists.
        Order-independent by default (multiset compare); --split-artists-ordered
        requires the same order. Empty on either side defers to the direct
        mismatch (returns False), so a real one-sided gap still surfaces."""
        p = self._artist_components(plex)
        r = self._artist_components(rb)
        if not p or not r:
            return False
        return p == r if self.match_artist_order else sorted(p) == sorted(r)

    # --- rendering ----------------------------------------------------------

    def _render(self, report: ParityReport) -> None:
        if self.as_json:
            self._render_json(report)
            return

        ignored_suffix = f", {report.ignored} ignored" if report.ignored else ""
        console.print(
            f"[bold green]✔ Scanned {report.scanned} Plex track(s):[/bold green] "
            f"{report.compared} mapped to Rekordbox, "
            f"{len(report.plex_orphans)} unmatched{ignored_suffix}.\n"
        )

        if report.mismatches:
            table = Table(title="Metadata mismatches (Rekordbox ↔ Plex)")
            table.add_column("#", justify="right", style="dim")
            table.add_column("ratingKey", justify="right", style="dim")
            table.add_column("Track")
            table.add_column("Field", style="yellow")
            table.add_column("Plex", style="cyan")
            table.add_column("Rekordbox", style="magenta")
            table.add_column("File", style="dim", overflow="fold")
            for i, m in enumerate(report.mismatches, 1):
                table.add_row(
                    str(i),
                    str(m["rk"]),
                    m["label"],
                    FIELD_LABELS[m["field"]],
                    _fmt(m["plex"]),
                    _fmt(m["rb"]),
                    _fmt(m["file"]),
                )
            console.print(table)

        if self.include_orphans:
            self._render_orphans(report)

        tracks_with_diffs = len({m["rk"] for m in report.mismatches})
        console.print(
            f"\n[bold]Compared[/bold] {report.compared} track(s) on fields: "
            f"{', '.join(FIELD_LABELS[f] for f in FIELD_LABELS if f in self.fields)}"
        )
        if report.ignored:
            console.print(
                f"[dim]Ignored {report.ignored} track(s) via "
                f"REKORDBOX_FOLDER_PATHS_TO_IGNORE[/dim]"
            )
        console.print(
            f"[bold]Mismatches:[/bold] {len(report.mismatches)} "
            f"across {tracks_with_diffs} track(s)"
        )
        if self.include_orphans:
            console.print(
                f"[bold]Plex tracks with no Rekordbox match:[/bold] "
                f"{len(report.plex_orphans)}"
            )
            console.print(
                f"[bold]Rekordbox tracks with no Plex match:[/bold] "
                f"{len(report.rb_orphan_ids)}"
            )

        if (
            not report.mismatches
            and not report.plex_orphans
            and (not self.include_orphans or not report.rb_orphan_ids)
        ):
            console.print("[bold green]✔ Rekordbox and Plex are in parity.")

    def _render_orphans(self, report: ParityReport) -> None:
        if report.plex_orphans:
            table = Table(
                title=f"Plex tracks with no Rekordbox match "
                f"(showing up to {self.orphan_limit})"
            )
            table.add_column("#", justify="right", style="dim")
            table.add_column("ratingKey", justify="right", style="dim")
            table.add_column("Title")
            table.add_column("File", style="dim")
            for i, o in enumerate(report.plex_orphans[: self.orphan_limit], 1):
                table.add_row(str(i), str(o["rk"]), _fmt(o["title"]), _fmt(o["file"]))
            console.print(table)

        if report.rb_orphan_ids:
            table = Table(
                title=f"Rekordbox tracks with no Plex match "
                f"(showing up to {self.orphan_limit})"
            )
            table.add_column("#", justify="right", style="dim")
            table.add_column("RB ID", justify="right", style="dim")
            table.add_column("Title")
            table.add_column("Artist", style="magenta")
            table.add_column("Path", style="dim", overflow="fold")
            for i, rb_id in enumerate(report.rb_orphan_ids[: self.orphan_limit], 1):
                meta = get_rb_metadata(rb_id) or {}
                table.add_row(
                    str(i),
                    str(rb_id),
                    _fmt(meta.get("title")),
                    _fmt(meta.get("artist")),
                    _fmt(meta.get("folder_path")),
                )
            console.print(table)

    def _render_json(self, report: ParityReport) -> None:
        """Emit the full report as JSON on stdout. Orphan lists are complete
        (the --orphan-limit cap is a table-display concern only)."""
        payload: Dict = {
            "fields": [f for f in FIELD_LABELS if f in self.fields],
            "scanned": report.scanned,
            "compared": report.compared,
            "ignored": report.ignored,
            "mismatches": [
                {
                    "ratingKey": m["rk"],
                    "field": m["field"],
                    "plex": m["plex"],
                    "rekordbox": m["rb"],
                    "track": m["label"],
                    "file": m["file"],
                }
                for m in report.mismatches
            ],
        }
        if self.include_orphans:
            payload["plex_orphans"] = [
                {"ratingKey": o["rk"], "title": o["title"], "file": o["file"]}
                for o in report.plex_orphans
            ]
            rb_orphans: List[Dict] = []
            for rb_id in report.rb_orphan_ids:
                meta = get_rb_metadata(rb_id) or {}
                rb_orphans.append(
                    {
                        "id": rb_id,
                        "title": meta.get("title"),
                        "artist": meta.get("artist"),
                        "path": meta.get("folder_path"),
                    }
                )
            payload["rekordbox_orphans"] = rb_orphans
        print(json.dumps(payload, indent=2, ensure_ascii=False))
