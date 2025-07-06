from ..PlexClient import plexapi_client
import os

def get_music_library_name():
    PLEX_LIBRARY_NAME = os.getenv("PLEX_LIBRARY_NAME")
    if not PLEX_LIBRARY_NAME:
        raise Exception("Env PLEX_LIBRARY_NAME missing")
    return PLEX_LIBRARY_NAME

def get_music_library():
    plexapi = plexapi_client()
    music_library_name = get_music_library_name()
    library = plexapi.library.section(music_library_name)
    return library, music_library_name
