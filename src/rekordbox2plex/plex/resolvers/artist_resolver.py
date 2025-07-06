from .library_resolver import get_music_library

def get_artist(rating_key):
    music_library, _ = get_music_library()
    return music_library.fetchItem(rating_key)

def get_all_artists():
    music_library, _ = get_music_library()
    return music_library.artists()

def search_for_artists(artist_name):
    music_library, _ = get_music_library()
    return music_library.search(artist_name, libtype="artist")
