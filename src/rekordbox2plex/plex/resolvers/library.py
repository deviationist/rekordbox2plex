from ..PlexClient import plexapi_client
from plexapi.library import LibrarySection
from typing import Tuple
import os


def get_music_library_name() -> str:
    PLEX_LIBRARY_NAME = os.getenv("PLEX_LIBRARY_NAME")
    if not PLEX_LIBRARY_NAME:
        raise Exception("Env PLEX_LIBRARY_NAME missing")
    return PLEX_LIBRARY_NAME


def plex_playlist_flattening_delimiter() -> str:
    PLEX_PLAYLIST_FLATTENING_DELIMITER = os.getenv("PLEX_PLAYLIST_FLATTENING_DELIMITER")
    if not PLEX_PLAYLIST_FLATTENING_DELIMITER:
        return "/"
    return PLEX_PLAYLIST_FLATTENING_DELIMITER


def get_music_library() -> Tuple[LibrarySection, str]:
    plexapi = plexapi_client()
    music_library_name = get_music_library_name()
    library = plexapi.library.section(music_library_name)
    return library, music_library_name


def update_library(path: str) -> None:
    """
    Update the Plex library for the given path.
    """
    library, _ = get_music_library()
    library.update(path)
