import os


def get_logger_name() -> str:
    LOGGER_NAME = os.getenv("LOGGER_NAME")
    if LOGGER_NAME:
        return LOGGER_NAME
    return "rekordbox2plex"


def get_db_path() -> str:
    DB_PATH = os.getenv("REKORDBOX_MASTERDB_PATH")
    if not DB_PATH:
        raise Exception("Env REKORDBOX_MASTERDB_PATH missing")
    return DB_PATH


def get_db_pass() -> str:
    DB_PASSWORD = os.getenv("REKORDBOX_MASTERDB_PASSWORD")
    if not DB_PASSWORD:
        raise Exception("Env REKORDBOX_MASTERDB_PASSWORD missing")
    return DB_PASSWORD
