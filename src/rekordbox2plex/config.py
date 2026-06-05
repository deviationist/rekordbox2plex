import os
import argparse
from typing import Optional, List, Set
from .utils.helpers import get_boolenv

_args: argparse.Namespace | None = None


def set_args(args: argparse.Namespace) -> None:
    global _args
    _args = args


def get_args() -> argparse.Namespace:
    if _args is None:
        raise RuntimeError("Arguments have not been initialized")
    return _args


def get_command() -> str:
    return get_args().command


def should_wipe() -> bool:
    return getattr(get_args(), "wipe", False)


def is_dry_run() -> bool:
    return getattr(get_args(), "dry_run", False)


def should_restore_dates() -> bool:
    return get_command() == "dates"


def get_validate_track() -> Optional[str]:
    return getattr(get_args(), "validate_track", None)


def get_validate_album() -> Optional[str]:
    return getattr(get_args(), "validate_album", None)


def should_write() -> bool:
    # --dry-run always wins: it forces a read-only run even if --write is given.
    return getattr(get_args(), "write", False) and not getattr(
        get_args(), "dry_run", False
    )


def get_plan_file() -> Optional[str]:
    """Optional path to dump the SQL plan for inspection. None = don't write a
    file (the default; the write itself streams SQL to Plex SQLite via stdin)."""
    return getattr(get_args(), "plan_file", None)


def get_only_rating_keys() -> Optional[Set[int]]:
    """Parse --only into a set of Plex ratingKeys, or None for the whole library.
    Accepts track and/or album ids (e.g. "17779,17776")."""
    raw = getattr(get_args(), "only", None)
    if not raw:
        return None
    ids = {int(p.strip()) for p in raw.split(",") if p.strip()}
    return ids or None


def should_include_tracks() -> bool:
    return getattr(get_args(), "tracks", True)


def should_include_albums() -> bool:
    return getattr(get_args(), "albums", True)


_PARITY_FIELDS = ("title", "artist", "album", "albumartist")


def get_parity_fields() -> Set[str]:
    """Which metadata fields the `parity` check compares. Defaults to all four.
    --fields takes a comma-separated subset of title,artist,album,albumartist."""
    raw = getattr(get_args(), "fields", None)
    if not raw:
        return set(_PARITY_FIELDS)
    chosen = {p.strip().lower() for p in raw.split(",") if p.strip()}
    unknown = chosen - set(_PARITY_FIELDS)
    if unknown:
        raise ValueError(
            f"Unknown parity field(s): {', '.join(sorted(unknown))}. "
            f"Valid: {', '.join(_PARITY_FIELDS)}"
        )
    return chosen or set(_PARITY_FIELDS)


def should_include_orphans() -> bool:
    """Whether `parity` reports tracks present in one system but not the other."""
    return getattr(get_args(), "orphans", True)


def get_orphan_limit() -> int:
    """Cap on the per-side orphan *sample* printed (counts are always full)."""
    return int(getattr(get_args(), "orphan_limit", 50))


def should_output_json() -> bool:
    """Whether `parity` emits a JSON document on stdout instead of tables."""
    return getattr(get_args(), "json", False)


def get_plex_db_path() -> Optional[str]:
    """Host path to com.plexapp.plugins.library.db. Optional: when unset the
    read-only DB cross-check is skipped and the write phase will error."""
    return os.getenv("PLEX_DB_PATH")


def get_plex_container_name() -> str:
    return os.getenv("PLEX_CONTAINER_NAME", "plex")


def get_rekordbox_tz() -> Optional[str]:
    """IANA tz name used to interpret *naive* Rekordbox timestamps. None = host
    local zone. Ignored for offset-aware timestamps (e.g. created_at)."""
    return os.getenv("REKORDBOX_TZ")


def get_rb_added_at_field() -> str:
    """Which djmdContent column feeds Plex added_at. Default created_at."""
    return os.getenv("REKORDBOX_ADDED_AT_FIELD", "created_at")


def get_plex_sqlite_mechanism() -> str:
    """How the write executes: 'docker' (bundled Plex SQLite in the stopped
    container's image — recommended) or 'sqlite3' (stock sqlite3, for writing
    to a scratch copy during verification)."""
    return os.getenv("PLEX_SQLITE_MECHANISM", "docker").lower()


def get_plex_docker_image() -> str:
    return os.getenv("PLEX_DOCKER_IMAGE", "linuxserver/plex")


def get_plex_sqlite_bin() -> str:
    return os.getenv("PLEX_SQLITE_BIN", "/usr/lib/plexmediaserver/Plex SQLite")


def should_allow_running() -> bool:
    """Bypass the container-stopped guard (only for scratch-copy testing)."""
    return getattr(get_args(), "allow_running", False)


def get_logger_name() -> str:
    LOGGER_NAME = os.getenv("LOGGER_NAME")
    if LOGGER_NAME:
        return LOGGER_NAME
    return "rekordbox2plex"


def should_delete_orphaned_playlists() -> bool:
    return get_boolenv("DELETE_ORPHANED_PLAYLISTS", False)


def get_playlists_to_ignore() -> List[str]:
    REKORDBOX_PLAYLISTS_TO_IGNORE = os.getenv("REKORDBOX_PLAYLISTS_TO_IGNORE")
    if not REKORDBOX_PLAYLISTS_TO_IGNORE:
        return []
    return [item.strip() for item in REKORDBOX_PLAYLISTS_TO_IGNORE.split(",")]


def get_rb_folder_paths_to_ignore() -> List[str]:
    """Rekordbox FolderPath prefixes to exclude from the `parity` check. A track
    whose Rekordbox FolderPath starts with any of these is skipped entirely (not
    compared, not reported as an orphan on either side). Comma-separated."""
    raw = os.getenv("REKORDBOX_FOLDER_PATHS_TO_IGNORE")
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_folder_mappings_path() -> Optional[str]:
    return os.getenv("FOLDER_MAPPINGS_PATH")


def get_db_path() -> str:
    DB_PATH = os.getenv("REKORDBOX_MASTERDB_PATH")
    if DB_PATH:
        return DB_PATH
    RB_FOLDER_PATH = os.getenv("REKORDBOX_FOLDER_PATH")
    if RB_FOLDER_PATH:
        return f"{RB_FOLDER_PATH.rstrip('/')}/master.db"
    raise Exception("Env REKORDBOX_MASTERDB_PATH missing")


def get_db_pass() -> str:
    DB_PASSWORD = os.getenv("REKORDBOX_MASTERDB_PASSWORD")
    if not DB_PASSWORD:
        raise Exception("Env REKORDBOX_MASTERDB_PASSWORD missing")
    return DB_PASSWORD
