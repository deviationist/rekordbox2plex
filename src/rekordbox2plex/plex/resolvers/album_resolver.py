from .library_resolver import get_music_library

def get_album(rating_key):
    music_library, _ = get_music_library()
    return music_library.fetchItem(rating_key)

def get_all_albums():
    music_library, _ = get_music_library()
    return music_library.search(libtype="album")
