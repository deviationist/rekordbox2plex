from .library import get_music_library
from ..data_types import PlexArtist, PlexArtists


def get_artist(artist_id: int) -> PlexArtist:
    music_library, _ = get_music_library()
    return music_library.fetchItem(artist_id)


def search_for_artists(artist_name) -> PlexArtists:
    music_library, _ = get_music_library()
    return music_library.search(artist_name, libtype="artist")
