from .library import get_music_library
from ..data_types import PlexTracks


def get_all_tracks() -> PlexTracks:
    music_library, _ = get_music_library()
    return music_library.searchTracks()
