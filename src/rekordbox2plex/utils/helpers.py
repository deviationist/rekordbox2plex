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

    # Imported lazily: config.py imports from this module, so a top-level
    # import would be circular. The parity field tuples are the single source
    # of truth for what --fields accepts and what it defaults to.
    from .. import config

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
        help="Comma-separated subset of {%s} to compare (default: %s). "
        "albumartist is opt-in: Rekordbox dedups albums by name, so its "
        "album-artist is per-album, not per-track, and unreliable for "
        "same-named releases."
        % (",".join(config.PARITY_FIELDS), ",".join(config.PARITY_DEFAULT_FIELDS)),
    )
    parity.add_argument(
        "--only",
        default=None,
        metavar="RATINGKEYS",
        help="Comma-separated Plex track ratingKeys to check only those.",
    )
    parity.add_argument(
        "--split-artists",
        action="store_true",
        dest="split_artists",
        help="On an artist/albumartist miss, retry by splitting BOTH sides into "
        "component artists (shared collab separators) and comparing the set — so "
        "'Fred V & Grafix' equals 'Fred V, Grafix'. Order-independent by default.",
    )
    parity.add_argument(
        "--split-artists-ordered",
        action="store_true",
        dest="split_artists_ordered",
        help="With --split-artists, require the components to match in the same "
        "order (default: order-independent, so 'A, B' equals 'B, A').",
    )
    parity.add_argument(
        "--collab-extra-seps",
        dest="collab_extra_seps",
        default=None,
        metavar="SEPS",
        help='Opt-in ambiguous separators (e.g. "& +") for --split-artists, so '
        "'Fred V & Grafix' splits. Empty/unset = off (comma + feat only). "
        "Overrides ARTIST_COLLAB_EXTRA_SEPARATORS.",
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

    # rekordbox2plex artist-images [--write] [--overwrite] [--providers ...] ...
    artist_images = subparsers.add_parser(
        "artist-images",
        parents=[common],
        help="Set Plex artist posters from external sources "
        "(driver-based; read-only unless --write).",
    )
    artist_images.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which posters would be set, without uploading (default).",
    )
    artist_images.add_argument(
        "--write",
        action="store_true",
        help="Upload the resolved posters to Plex (requires confirmation).",
    )
    artist_images.add_argument(
        "--overwrite",
        action="store_true",
        help="Also replace artists that already have a poster "
        "(default: only fill artists with none).",
    )
    artist_images.add_argument(
        "--providers",
        default=None,
        metavar="LIST",
        help="Comma-separated provider order, overriding PLEX_ARTIST_IMAGE_PROVIDERS "
        "(known: fanarttv,theaudiodb,deezer,spotify,discogs).",
    )
    artist_images.add_argument(
        "--only",
        default=None,
        metavar="RATINGKEYS",
        help="Comma-separated Plex artist ratingKeys to limit to.",
    )
    artist_images.add_argument(
        "--limit",
        default=None,
        type=int,
        metavar="N",
        help="Process at most N artists this run.",
    )
    artist_images.add_argument(
        "--threads",
        default=None,
        type=int,
        metavar="N",
        help="Concurrent workers for matching + uploading (default 8; 1 = serial).",
    )
    artist_images.add_argument(
        "--collab-mode",
        dest="collab_mode",
        choices=["skip", "primary", "collage"],
        default="skip",
        help="Handle multi-artist 'A, B, C' strings that match no single artist: "
        "skip (default), primary (first member's portrait), or collage "
        "(composite each member's portrait into one poster).",
    )
    artist_images.add_argument(
        "--collab-extra-seps",
        dest="collab_extra_seps",
        default=None,
        metavar="SEPS",
        help='Opt-in last-resort separators (e.g. "& +") to also split a collab '
        "name on, but ONLY after the full string and each component miss every "
        "source (so 'Above & Beyond' stays whole). Empty/unset = off. Overrides "
        "ARTIST_COLLAB_EXTRA_SEPARATORS.",
    )

    # rekordbox2plex clear-art [--kind ...] [--write] [--only ...] [--allow-running]
    clear_art = subparsers.add_parser(
        "clear-art",
        parents=[common],
        help="Remove uploaded artist/album posters via a direct Plex DB write "
        "(Plex must be stopped; read-only unless --write).",
    )
    clear_art.add_argument(
        "--kind",
        choices=["artist", "album", "both"],
        default="artist",
        help="Which uploaded posters to clear: artist (default), album, or both.",
    )
    clear_art.add_argument(
        "--dry-run",
        action="store_true",
        help="List the posters that would be cleared, without writing "
        "(also the default; overrides --write).",
    )
    clear_art.add_argument(
        "--write",
        action="store_true",
        help="Clear the posters in the Plex DB (Plex must be stopped; "
        "requires the CLEAR-IMAGES token).",
    )
    clear_art.add_argument(
        "--only",
        default=None,
        metavar="RATINGKEYS",
        help="Comma-separated Plex ratingKeys to clear only those "
        "(default: every item of the selected kind with an uploaded poster).",
    )
    clear_art.add_argument(
        "--keep-files",
        action="store_true",
        dest="keep_files",
        help="Only clear the DB selection; leave the uploaded image file on disk "
        "(default: also delete the orphaned file from the Plex bundle).",
    )
    clear_art.add_argument(
        "--allow-running",
        action="store_true",
        help="Bypass the container-stopped guard (only for scratch-copy testing).",
    )

    # rekordbox2plex lossless-tags --root DIR [--write] [--delete-lossy] ...
    lossless_tags = subparsers.add_parser(
        "lossless-tags",
        parents=[common],
        help="Copy ID3 tags from a lossy file onto a same-named lossless "
        "replacement (AIFF) in the same folder (read-only unless --write).",
    )
    lossless_tags.add_argument(
        "--root",
        default=None,
        metavar="DIR",
        help="Music root to walk for lossy/lossless pairs (env MUSIC_ROOT).",
    )
    lossless_tags.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the tag diff per matched pair without writing "
        "(also the default; overrides --write).",
    )
    lossless_tags.add_argument(
        "--write",
        action="store_true",
        help="Copy the tags onto the lossless files (requires the WRITE-TAGS token).",
    )
    lossless_tags.add_argument(
        "--show",
        choices=["matched", "unmatched", "both"],
        default="matched",
        help="Which lossy files to list: matched (have a lossless sibling; "
        "default), unmatched (not yet upgraded), or both.",
    )
    lossless_tags.add_argument(
        "--lossy-exts",
        dest="lossy_exts",
        default=None,
        metavar="EXTS",
        help="Comma-separated lossy source extensions (default '.mp3').",
    )
    lossless_tags.add_argument(
        "--lossless-exts",
        dest="lossless_exts",
        default=None,
        metavar="EXTS",
        help="Comma-separated lossless target extensions (default '.aiff,.aif'; "
        "only AIFF/AIFF-C are supported — FLAC/WAV are skipped).",
    )
    lossless_tags.add_argument(
        "--remove-name",
        action="store_true",
        dest="remove_name",
        help="Strip the AIFF NAME chunk instead of setting it to the copied title.",
    )
    lossless_tags.add_argument(
        "--refresh-plex",
        action="store_true",
        dest="refresh_plex",
        help="After writing, trigger a partial Plex scan of the affected "
        "directories (needs PLEX_MEDIA_PATH_MAP + Plex API connection).",
    )
    lossless_tags.add_argument(
        "--delete-lossy",
        action="store_true",
        dest="delete_lossy",
        help="Delete the lossy source after a fully successful copy "
        "(default: leave it for you to remove manually).",
    )
    lossless_tags.add_argument(
        "--mirror-version",
        action="store_true",
        dest="mirror_version",
        help="Save ID3 as the source's major version instead of forcing v2.3.",
    )
    lossless_tags.add_argument(
        "--ignore-case",
        action="store_true",
        dest="ignore_case",
        help="Match basenames case-insensitively (default: exact match).",
    )
    lossless_tags.add_argument(
        "--snapshot-dates",
        action="store_true",
        dest="snapshot_dates",
        help="While copying, capture each lossy file's Rekordbox 'Date Added' into "
        "the rb-dates sidecar (read-only) so it can be restored after you re-add "
        "the lossless file in Rekordbox.",
    )
    lossless_tags.add_argument(
        "--limit",
        default=None,
        type=int,
        metavar="N",
        help="Process at most N matched pairs this run.",
    )
    lossless_tags.add_argument(
        "--backup-dir",
        default=None,
        dest="backup_dir",
        help="Directory to back up lossless originals before the ID3 overwrite "
        "(default: ./lossless-tag-backups).",
    )

    # rekordbox2plex rb-dates {snapshot,apply} ...
    rb_dates = subparsers.add_parser(
        "rb-dates",
        parents=[common],
        help="Preserve Rekordbox 'Date Added' across a lossy→lossless swap: "
        "snapshot the old date, then restore it onto the re-added file.",
    )
    rb_modes = rb_dates.add_subparsers(dest="rb_dates_mode", required=True)

    rb_snapshot = rb_modes.add_parser(
        "snapshot",
        parents=[common],
        help="Capture each lossy file's Rekordbox Date Added into the sidecar "
        "(read-only).",
    )
    rb_snapshot.add_argument(
        "--root",
        default=None,
        metavar="DIR",
        help="Music root to walk for lossy/lossless pairs (env MUSIC_ROOT).",
    )
    rb_snapshot.add_argument(
        "--snapshot-file",
        dest="snapshot_file",
        default=None,
        help="Sidecar JSON path (env RB_DATE_SNAPSHOT_PATH; "
        "default ./rb-date-snapshots.json).",
    )
    rb_snapshot.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be captured without writing the sidecar.",
    )
    rb_snapshot.add_argument(
        "--lossy-exts",
        dest="lossy_exts",
        default=None,
        metavar="EXTS",
        help="Comma-separated lossy source extensions (default '.mp3').",
    )
    rb_snapshot.add_argument(
        "--lossless-exts",
        dest="lossless_exts",
        default=None,
        metavar="EXTS",
        help="Comma-separated lossless target extensions (default '.aiff,.aif').",
    )
    rb_snapshot.add_argument(
        "--ignore-case",
        dest="ignore_case",
        action="store_true",
        help="Match basenames case-insensitively (default: exact match).",
    )

    rb_apply = rb_modes.add_parser(
        "apply",
        parents=[common],
        help="Restore captured dates onto the re-added Rekordbox rows "
        "(read-only unless --write; Rekordbox must be closed everywhere).",
    )
    rb_apply.add_argument(
        "--snapshot-file",
        dest="snapshot_file",
        default=None,
        help="Sidecar JSON path (env RB_DATE_SNAPSHOT_PATH; "
        "default ./rb-date-snapshots.json).",
    )
    rb_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the old→restored date table without writing (also the "
        "default; overrides --write).",
    )
    rb_apply.add_argument(
        "--write",
        action="store_true",
        help="Write the dates into the Rekordbox DB (requires the WRITE-RB-DATES "
        "token; Rekordbox closed + Resilio idle).",
    )
    rb_apply.add_argument(
        "--backup-dir",
        dest="backup_dir",
        default=None,
        help="Where to back up master.db before writing "
        "(env RB_DATE_BACKUP_DIR; default ./rekordbox-db-backups).",
    )
    rb_apply.add_argument(
        "--ignore-wal",
        dest="ignore_wal",
        action="store_true",
        help="Proceed even if a non-empty master.db-wal exists (advanced — "
        "normally means Rekordbox is still open).",
    )
    rb_apply.add_argument(
        "--stability-wait",
        dest="stability_wait",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Seconds the quiescence probe waits between stat samples (default 5).",
    )
    rb_apply.add_argument(
        "--keep-applied",
        dest="keep_applied",
        action="store_true",
        help="Keep restored entries in the sidecar instead of pruning them.",
    )
    rb_apply.add_argument(
        "--allow-running",
        action="store_true",
        help="Bypass the open/stability guards (only for scratch-copy testing).",
    )
    return parser.parse_args()
