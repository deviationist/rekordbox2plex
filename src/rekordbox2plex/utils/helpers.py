import argparse
from typing import List, Any
from ..plex.data_types import PlexTrackWrapper
import os
from datetime import datetime
from .. import config
from .confirm import confirm_warning

VALID_TARGET_CHOICES = {"all", "tracks", "playlists", "albums"}


def check_for_dangerous_config():
    if config.should_wipe():
        confirm_warning(
            "You have flagged to wipe all Plex-items. Are you want to continue?"
        )
    if config.plex_track_lookup_override() and config.should_delete_orphaned_tracks():
        confirm_warning(
            "You have overriden the Plex track lookup (env PLEX_TRACK_LOOKUP_OVERRIDE), and orphaned track deletion is active. (env DELETE_ORPHANED_TRACKS). Do you want to continue?"
        )
    if (
        config.plex_playlist_lookup_override()
        and config.should_delete_orphaned_playlists()
    ):
        confirm_warning(
            "You have overriden the Plex playlist lookup (env PLEX_PLAYLIST_LOOKUP_OVERRIDE), and orphaned trplaylistack deletion is active. (env DELETE_ORPHANED_PLAYLISTS). Do you want to continue?"
        )
    if config.plex_album_lookup_override() and config.should_delete_orphaned_albums():
        confirm_warning(
            "You have overriden the Plex album lookup (env PLEX_ALBUM_LOOKUP_OVERRIDE), and orphaned track deletion is active. (env DELETE_ORPHANED_ALBUMS). Do you want to continue?"
        )


def get_boolenv(key: str, default: bool | str) -> bool:
    return str_to_bool(os.getenv(key, default))


def is_valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def progress_count(current_number: int, total_count: int) -> str:
    return f"{current_number+1}/{total_count}"


def should_lock_fields() -> bool:
    return get_boolenv("PLEX_LOCK_FIELDS", True)


def field_is_locked(plex_item: Any, field_name: str) -> bool:
    field = next((p for p in plex_item.fields if p.name == field_name), None)
    if not field:
        return False
    return field.locked


def str_to_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in ("1", "true", "yes", "on")


def build_track_string(plex_track: PlexTrackWrapper) -> str:
    return f'"{plex_track.track_title}" by "{plex_track.track_artist_name}"'


def determine_targets(args) -> tuple[List[str], bool]:
    affect_all = (
        args.targets is None
        or "all" in args.targets
        or len(args.targets) >= (len(VALID_TARGET_CHOICES) - 1)
    )
    actions = []
    if (args.targets and "tracks" in args.targets) or affect_all:
        actions.append("tracks")
    if (args.targets and "playlists" in args.targets) or affect_all:
        actions.append("playlists")
    if (args.targets and "albums" in args.targets) or affect_all:
        actions.append("albums")
    return actions, affect_all


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
        "--wipe",
        action="store_true",
        help="Delete all items in Plex.",
    )

    parser.add_argument(
        "--targets",
        type=parse_sync_arg,
        help=f'Comma-separated list of what to target: {", ".join(VALID_TARGET_CHOICES)}',
    )

    return parser.parse_args()
