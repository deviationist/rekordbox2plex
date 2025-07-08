import os
import argparse
from typing import Optional

_args: argparse.Namespace | None = None


def set_args(args: argparse.Namespace) -> None:
    global _args
    _args = args


def get_args() -> argparse.Namespace:
    if _args is None:
        raise RuntimeError("Arguments have not been initialized")
    return _args


def is_dry_run() -> bool:
    return get_args().dry_run


def get_logger_name() -> str:
    LOGGER_NAME = os.getenv("LOGGER_NAME")
    if LOGGER_NAME:
        return LOGGER_NAME
    return "rekordbox2plex"


def get_rekordbox_folder_path() -> Optional[str]:
    return os.getenv("REKORDBOX_FOLDER_PATH")


def get_db_path() -> str:
    DB_PATH = os.getenv("REKORDBOX_MASTERDB_PATH")
    if not DB_PATH:
        RB_FOLDER_PATH = get_rekordbox_folder_path()
        if RB_FOLDER_PATH:
            return f"{RB_FOLDER_PATH.rstrip('/')}/master.db"
        raise Exception("Env REKORDBOX_MASTERDB_PATH missing")
    return DB_PATH


def get_db_pass() -> str:
    DB_PASSWORD = os.getenv("REKORDBOX_MASTERDB_PASSWORD")
    if not DB_PASSWORD:
        raise Exception("Env REKORDBOX_MASTERDB_PASSWORD missing")
    return DB_PASSWORD
