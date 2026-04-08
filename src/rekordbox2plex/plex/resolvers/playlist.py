from ... import config
from .library import get_music_library
from ..data_types import PlexPlaylist, PlexPlaylists


def get_playlist(playlist_id: int) -> PlexPlaylist:
    music_library, _ = get_music_library()
    return music_library.fetchItem(playlist_id)


def get_all_playlists() -> PlexPlaylists:
    music_library, _ = get_music_library()
    playlists = music_library.playlists(smart=False)
    if playlists:
        playlist_override = config.plex_playlist_lookup_override()
        if playlist_override:
            return [
                playlist
                for playlist in playlists
                if playlist.title == playlist_override
            ]
        return playlists
    return []
