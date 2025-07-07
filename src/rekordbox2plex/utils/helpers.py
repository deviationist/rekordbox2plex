import argparse
from ..plex.data_types import PlexTrackWrapper

VALID_TARGET_CHOICES = {"tracks", "playlists", "albums"}


def build_track_string(plex_track: PlexTrackWrapper) -> str:
    return f'"{plex_track.title}" by "{plex_track.track_artist}"'


def determine_sync_targets(args, default_target: str = "tracks") -> str:
    return args.sync if args.sync else default_target


def parse_sync_arg(s):
    items = [item.strip() for item in s.split(",")]
    invalid = set(items) - VALID_TARGET_CHOICES
    if invalid:
        raise argparse.ArgumentTypeError(
            f'Invalid choices: {", ".join(invalid)}. Valid options are: {", ".join(VALID_TARGET_CHOICES)}'
        )
    return items


def parse_script_arguments():
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
