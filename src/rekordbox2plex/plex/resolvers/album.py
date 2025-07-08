from .library import get_music_library
from ..data_types import PlexAlbum, PlexAlbums


def get_album(album_id: int) -> PlexAlbum:
    music_library, _ = get_music_library()
    return music_library.fetchItem(album_id)


def get_all_albums() -> PlexAlbums:
    music_library, _ = get_music_library()
    return music_library.search(libtype="album")
