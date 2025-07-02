from .client import main as plexapi_client
import os

PLEX_LIBRARY_NAME = os.getenv("PLEX_LIBRARY_NAME")

def get_music_library():
    plexapi = plexapi_client()
    library = plexapi.library.section(PLEX_LIBRARY_NAME)
    return library, PLEX_LIBRARY_NAME
