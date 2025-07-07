# from ..plex.repositories.ArtistRepository import ArtistRepository
# from ..plex.repositories.AlbumRepository import AlbumRepository
from ..utils.logger import logger
from typing import Any, Literal
from ..rekordbox.data_types import ResolvedAlbumWithTracks
from ..plex.data_types import Album
import pprint


class AlbumMetadataMapper:
    FORCE_UPDATE = True

    def __init__(self, plex_album: Album, rb_lookup: ResolvedAlbumWithTracks):
        self.rb_item = rb_lookup
        self.plex_album = plex_album
        self.album_artist_rating_key = None
        self.edits: dict[str, Any] = {}

    def resolve_release_year(self) -> Literal[False] | int:
        years = []
        for track in self.rb_item.tracks:
            years.append(track.release_year)
        years = list(set(years))
        if len(years) == 1:
            return int(years[0])
        return False

    def update_year(self):
        release_year = self.resolve_release_year()
        if release_year:
            self.edits["year.value"] = release_year
            logger.info(f'Setting album year to "{release_year}"')

    def update_artwork(self):
        pass
        # TODO: Resolve the Rb album and the release date (from the tracks?)
        #if self.rb_item.tracks:
        #    pprint.pprint(self.rb_item.tracks)
        # pprint.pprint(self.rb_artist)
        # pprint.pprint(self.rb_album)
        # pprint.pprint(self.rb_artwork)
        # artist.name
        # plex_album.title
        # "snowfall""Øneheart, reidenshi"
        # pprint.pprint(self.plex_album.__dict__)
        # pprint.pprint(self.plex_album.tracks()[0].__dict__)
        # rb_album_item = None
        # self.edits = {}
        # print(self.plex_album.year)
        # self.edits["year.value"] = 2022
        # self.update_track_title()
        # self.update_track_artist()
        # self.update_album_artist()
        # self.update_album()

    def transfer(self):
        self.update_year()
        self.update_artwork()
        return self

    def save(self):
        # self.plex_album.edit(**self.edits)
        # self.plex_album.reload()
        # print(self.plex_album.year)
        return ""
