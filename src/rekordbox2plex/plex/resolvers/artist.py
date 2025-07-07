from .library import get_music_library
from ..data_types import PlexArtist, PlexArtists


def get_artist(rating_key: int) -> PlexArtist:
    music_library, _ = get_music_library()
    return music_library.fetchItem(rating_key)


def search_for_artists(artist_name) -> PlexArtists:
    music_library, _ = get_music_library()
    return music_library.search(artist_name, libtype="artist")
