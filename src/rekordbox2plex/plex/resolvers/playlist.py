from ..PlexClient import plexapi_client
from .library import get_music_library
from ..data_types import PlexPlaylist, PlexPlaylists

def get_playlist(playlist_id: int) -> PlexPlaylist:
    music_library, _ = get_music_library()
    return music_library.fetchItem(playlist_id)

def get_all_playlists() -> PlexPlaylists:
    plexapi = plexapi_client()
    return plexapi.playlists(smart=False)
