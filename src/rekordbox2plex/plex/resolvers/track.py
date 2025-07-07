from .library import get_music_library
from ..data_types import PlexTrack, PlexTracks


def get_track(track_id: int) -> PlexTrack:
    music_library, _ = get_music_library()
    return music_library.fetchItem(track_id)


def get_all_tracks() -> PlexTracks:
    music_library, _ = get_music_library()
    return music_library.searchTracks()
