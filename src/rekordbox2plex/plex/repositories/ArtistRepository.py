from ._RepositoryBase import RepositoryBase, singleton
from ..resolvers.artist import get_artist, search_for_artists
from ..data_types import PlexArtist


@singleton
class ArtistRepository(RepositoryBase):
    def __init__(self) -> None:
        super().__init__(True)

    def get_artist(self, artist_id: int, use_cache: bool = True) -> PlexArtist:
        if (
            use_cache
            and self._search_cache
            and (cached_artist := self._get_from_cache(str(artist_id)))
        ):
            return cached_artist
        if artist := get_artist(artist_id):
            if use_cache:
                self._store_single_in_cache(artist)
            return artist
        return None

    def search_for_artists(
        self, artist_name: str, use_cache: bool = True
    ) -> list[PlexArtist]:
        if (
            use_cache
            and self._search_cache
            and (cached_artist_search := self._search_cache.get_from_cache(artist_name))
        ):
            return cached_artist_search
        results = search_for_artists(artist_name)
        if results:
            if use_cache and self._search_cache:
                self._search_cache.store_in_cache(artist_name, results)
            return results
        return []

    def search_for_artist(
        self, artist_name: str, exact_match: bool = True
    ) -> PlexArtist:
        results = self.search_for_artists(artist_name)
        if results and len(results) > 0:
            if exact_match:
                exact_matches = [
                    artist for artist in results if artist.title == artist_name
                ]
                if exact_matches and len(exact_matches) > 0:
                    return exact_matches[0]  # We got at least one hit, return it
                return None  # No exact match in hits
            return results[0]  # We got at least one hit, return it
        return None  # No hits
