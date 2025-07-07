from ._RepositoryBase import RepositoryBase, singleton
from ..resolvers.library import get_music_library
from ..resolvers.playlist import get_playlist, get_all_playlists
from ..data_types import Track, PlexPlaylist, PlexPlaylists
from typing import List

@singleton
class PlaylistRepository(RepositoryBase):
    def get_playlist(self, playlist_id: int) -> PlexPlaylist:
        return get_playlist(playlist_id)

    def get_all_playlists(self) -> PlexPlaylists:
        return get_all_playlists()

    def create_playlist(self, playlist_name: str, items: List[Track]):
        music_library, _ = get_music_library()
        music_library.createPlaylist(playlist_name, items=items)
