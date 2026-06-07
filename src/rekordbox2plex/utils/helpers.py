import argparse
import os
from ..plex.data_types import PlexTrackWrapper


def get_boolenv(key: str, default: bool | str) -> bool:
    return str_to_bool(os.getenv(key, default))


def str_to_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in ("1", "true", "yes", "on")


def progress_count(current_number: int, total_count: int) -> str:
    return f"{current_number+1}/{total_count}"


def build_track_string(plex_track: PlexTrackWrapper) -> str:
    return f'"{plex_track.track_title}" by "{plex_track.track_artist_name}"'


def parse_script_arguments() -> argparse.Namespace:
    # -v/--verbose is shared by every subcommand via this parent parser, so it
    # can be given after the subcommand name (e.g. `rekordbox2plex dates -v`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity: -v = INFO, -vv = DEBUG",
    )

    parser = argparse.ArgumentParser(prog="rekordbox2plex")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # rekordbox2plex playlists [--dry-run] [--wipe]
    playlists = subparsers.add_parser(
        "playlists",
        parents=[common],
        help="Sync Rekordbox playlists into Plex.",
    )
    playlists.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the actions without making changes.",
    )
    playlists.add_argument(
        "--wipe",
        action="store_true",
        help="Delete all playlists in Plex (requires typed confirmation).",
    )

    # rekordbox2plex dates [--write] [--validate-*] [--tracks/--albums] ...
    dates = subparsers.add_parser(
        "dates",
        parents=[common],
        help="Sync Plex 'Date Added' from Rekordbox (read-only unless --write).",
    )
    dates.add_argument(
        "--validate-track",
        default=None,
        help="Phase 0: validate a single track by Plex ratingKey (read-only).",
    )
    dates.add_argument(
        "--validate-album",
        default=None,
        help="Phase 0: validate a single album by Plex ratingKey (read-only).",
    )
    dates.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing (this is also the default; overrides --write).",
    )
    dates.add_argument(
        "--write",
        action="store_true",
        help="Apply the plan to the Plex DB (Plex must be stopped; requires confirmation).",
    )
    dates.add_argument(
        "--allow-running",
        action="store_true",
        help="Bypass the container-stopped guard (only for scratch-copy testing).",
    )
    dates.add_argument(
        "--plan-file",
        default=None,
        help="Optional: also dump the SQL plan to this file for inspection (off by default).",
    )
    dates.add_argument(
        "--only",
        default=None,
        metavar="RATINGKEYS",
        help="Comma-separated Plex ratingKeys to sync only those items "
        "(track and/or album ids), e.g. --only 17779,17776.",
    )
    dates.add_argument(
        "--tracks",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include track-level updates (default on; --no-tracks to skip).",
    )
    dates.add_argument(
        "--albums",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include album-level updates (default on; --no-albums to skip).",
    )

    # rekordbox2plex parity [--fields ...] [--only ...] [--no-orphans] ...
    parity = subparsers.add_parser(
        "parity",
        parents=[common],
        help="Read-only check that Title/Artist/Album/AlbumArtist match between "
        "Rekordbox and Plex (reads both DBs, never writes).",
    )
    parity.add_argument(
        "--fields",
        default=None,
        metavar="FIELDS",
        help="Comma-separated subset of title,artist,album,albumartist to "
        "compare (default: all four).",
    )
    parity.add_argument(
        "--only",
        default=None,
        metavar="RATINGKEYS",
        help="Comma-separated Plex track ratingKeys to check only those.",
    )
    parity.add_argument(
        "--orphans",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Report tracks present in one system but not the other "
        "(default on; --no-orphans to skip).",
    )
    parity.add_argument(
        "--orphan-limit",
        type=int,
        default=50,
        metavar="N",
        dest="orphan_limit",
        help="Cap the per-side orphan sample shown (counts are always full).",
    )
    parity.add_argument(
        "--json",
        action="store_true",
        help="Emit the full report as JSON on stdout instead of tables "
        "(orphan lists are complete, not capped).",
    )

    # rekordbox2plex aiff-titles [--write] [--remove-name] [--refresh-plex] ...
    aiff_titles = subparsers.add_parser(
        "aiff-titles",
        parents=[common],
        help="Fix AIFF titles where the legacy NAME chunk shadows ID3 in Plex "
        "(read-only unless --write).",
    )
    aiff_titles.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the NAME→ID3 title diff as a table without writing "
        "(also the default; overrides --write).",
    )
    aiff_titles.add_argument(
        "--write",
        action="store_true",
        help="Rewrite the AIFF NAME chunk on disk (requires confirmation).",
    )
    aiff_titles.add_argument(
        "--remove-name",
        action="store_true",
        dest="remove_name",
        help="Delete the NAME chunk instead of setting it to the ID3 title.",
    )
    aiff_titles.add_argument(
        "--refresh-plex",
        action="store_true",
        dest="refresh_plex",
        help="After writing, trigger album-level Refresh Metadata via the Plex API.",
    )
    aiff_titles.add_argument(
        "--only",
        default=None,
        metavar="RATINGKEYS",
        help="Comma-separated Plex track ratingKeys to limit to, e.g. --only 11553.",
    )
    aiff_titles.add_argument(
        "--backup-dir",
        default=None,
        dest="backup_dir",
        help="Directory to back up originals before editing "
        "(default: ./aiff-title-backups).",
    )
    return parser.parse_args()
