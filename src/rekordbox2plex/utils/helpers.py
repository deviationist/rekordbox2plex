import argparse
from typing import List
from ..plex.data_types import PlexTrackWrapper
import os

VALID_TARGET_CHOICES = {"all", "tracks", "playlists", "albums"}


def get_boolenv(key: str, default: bool | str) -> bool:
    return str_to_bool(os.getenv(key, default))


def str_to_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in ("1", "true", "yes", "on")


def build_track_string(plex_track: PlexTrackWrapper) -> str:
    return f'"{plex_track.title}" by "{plex_track.track_artist}"'


def determine_sync_targets(args) -> tuple[List[str], bool]:
    sync_all = (
        args.sync is None
        or "all" in args.sync
        or len(args.sync) >= (len(VALID_TARGET_CHOICES) - 1)
    )
    sync_actions = []
    if (args.sync and "tracks" in args.sync) or sync_all:
        sync_actions.append("tracks")
    if (args.sync and "playlists" in args.sync) or sync_all:
        sync_actions.append("playlists")
    if (args.sync and "albums" in args.sync) or sync_all:
        sync_actions.append("albums")
    return sync_actions, sync_all


def parse_sync_arg(s) -> List[str]:
    items = [item.strip() for item in s.split(",")]
    invalid = set(items) - VALID_TARGET_CHOICES
    if invalid:
        raise argparse.ArgumentTypeError(
            f'Invalid choices: {", ".join(invalid)}. Valid options are: {", ".join(VALID_TARGET_CHOICES)}'
        )
    return items


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
        "--sync",
        type=parse_sync_arg,
        help=f'Comma-separated list of what to sync: {", ".join(VALID_TARGET_CHOICES)}',
    )

    return parser.parse_args()
