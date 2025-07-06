from ._RepositoryBase import RepositoryBase, singleton
from ..resolvers.library_resolver import get_music_library
from ..resolvers.playlist_resolver import get_playlist, get_all_playlists

@singleton
class PlaylistRepository(RepositoryBase):
    def get_playlist(self, playlist_id: str):
        return get_playlist(playlist_id)

    def get_all_playlists():
        return get_all_playlists()

    def create_playlist(playlist_name, items):
        music_library, _ = get_music_library()
        music_library.createPlaylist(playlist_name, items=items)
