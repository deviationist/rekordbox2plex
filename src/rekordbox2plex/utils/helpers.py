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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity: -v = INFO, -vv = DEBUG",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the actions without making changes.",
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete all playlists in Plex (requires typed confirmation).",
    )
    return parser.parse_args()
