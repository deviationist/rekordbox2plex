import os
import argparse
from typing import Optional, List
from .utils.helpers import get_boolenv

_args: argparse.Namespace | None = None


def set_args(args: argparse.Namespace) -> None:
    global _args
    _args = args


def get_args() -> argparse.Namespace:
    if _args is None:
        raise RuntimeError("Arguments have not been initialized")
    return _args


def should_wipe() -> bool:
    return get_args().wipe


def is_dry_run() -> bool:
    return get_args().dry_run


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
