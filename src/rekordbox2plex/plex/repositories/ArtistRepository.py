from ._RepositoryBase import RepositoryBase, singleton
from ..resolvers.artist import get_artist, search_for_artists
from ..data_types import PlexArtist

@singleton
class ArtistRepository(RepositoryBase):
    def get_artist(self, artist_id: int, use_cache: bool = True) -> PlexArtist:
        if use_cache and (cached_artist := self._get_from_cache(str(artist_id))):
            return cached_artist
        if artist := get_artist(artist_id):
            self._store_single_in_cache(artist)
            return artist
        return False

    #def get_all_artists(self, use_cache: bool = True):
    #    if use_cache and self._all_fetched and (cached_artists := self._get_all_cache()):
    #        return cached_artists
    #    artists = get_all_artists()
    #    self._store_in_cache(artists)
    #    return artists

    def search_for_artist(self, artist_name: str) -> bool | tuple:
        results = search_for_artists(artist_name)
        if results and len(results) > 0:
            return results[0]
        return False
