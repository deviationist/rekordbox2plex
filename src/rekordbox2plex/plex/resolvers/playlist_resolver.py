from ..PlexClient import plexapi_client
from .library_resolver import get_music_library

def get_playlist(playlist_id):
    music_library, _ = get_music_library()
    return music_library.fetchItem(playlist_id)

def get_all_playlists():
    plexapi = plexapi_client()
    return plexapi.playlists(smart=False)
