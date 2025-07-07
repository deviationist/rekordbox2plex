from ._RepositoryBase import RepositoryBase, singleton
from ..resolvers.album import get_album, get_all_albums
from .ArtistRepository import ArtistRepository
from ..data_types import PlexAlbum, PlexAlbums


@singleton
class AlbumRepository(RepositoryBase):
    def get_album(self, album_id: int, use_cache: bool = True) -> PlexAlbum:
        if use_cache and (cached_album := self._get_from_cache(str(album_id))):
            return cached_album
        if album := get_album(album_id):
            self._store_single_in_cache(album)
            return album
        return None

    def get_all_albums(self, use_cache=True) -> PlexAlbums:
        if use_cache and self._all_fetched and (cached_albums := self._get_all_cache()):
            return cached_albums
        albums = get_all_albums()
        self._store_in_cache(albums)
        return albums

    def get_albums_by_artist(
        self, artist_id: int, use_cache: bool = True
    ) -> PlexAlbums:
        artist_albums = []
        if use_cache and self._all_fetched and (cached_albums := self._get_all_cache()):
            for cached_album in cached_albums:
                if cached_album.parentRatingKey == artist_id:
                    artist_albums.append(cached_album)
            return artist_albums
        if artist := ArtistRepository().get_artist(artist_id):
            artist_albums = artist.albums()
            self._append_to_cache(artist_albums)
            return artist_albums
        return None

    def search_for_album_by_artist(self, artist_id: int, album_name: str):
        return ""
