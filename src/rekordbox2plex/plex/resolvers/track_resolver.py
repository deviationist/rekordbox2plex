from .library_resolver import get_music_library

def get_track(track_id):
    music_library, _ = get_music_library()
    return music_library.fetchItem(track_id)

def get_all_tracks():
    music_library, _ = get_music_library()
    return music_library.searchTracks()
