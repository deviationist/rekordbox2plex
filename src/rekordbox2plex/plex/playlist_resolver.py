from .client import main as plexapi_client
from .library_resolver import get_music_library
from rich.console import Console
import os

PLEX_LIBRARY_NAME = os.getenv("PLEX_LIBRARY_NAME")
console = Console()

def get_all_playlists():
    plexapi = plexapi_client()
    return plexapi.playlists()

def create_playlist(playlist_name, items):
    music_library, library_name = get_music_library()
    music_library.createPlaylist(playlist_name, items=items)
