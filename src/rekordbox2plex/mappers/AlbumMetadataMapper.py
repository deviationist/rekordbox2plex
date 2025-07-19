from ..utils.logger import logger
from ..utils.helpers import get_boolenv
from ..config import is_dry_run
from typing import Any, Literal
from ..rekordbox.data_types import ResolvedAlbumWithTracks
from ..plex.data_types import Album
from ..utils.ArtworkResolver import ArtworkResolver


class AlbumMetadataMapper:
    def __init__(self, plex_album: Album, rb_lookup: ResolvedAlbumWithTracks):
        self.resolved_artwork_path = None
        self.rb_item = rb_lookup
        self.plex_album = plex_album
        self.album_artist_id = None
        self.did_update = False
        self.edits: dict[str, Any] = {}

    def resolve_release_year(self) -> Literal[False] | int:
        years = []
        for track in self.rb_item.tracks:
            years.append(track.release_year)
        years = list(set(years))
        unique_count = len(years)
        if unique_count == 1:
            return int(years[0])
        return False

    def update_year(self):
        release_year = self.resolve_release_year()
        if release_year and release_year != self.plex_album.year:
            self.edits["year.value"] = release_year
            self.did_update = True
            logger.debug(
                f'Setting album year to "{release_year}" for album "{self.plex_album.title}"'
            )

    def update_artwork(self):
        if self.plex_album.thumb and not get_boolenv("OVERWRITE_EXISTING_ALBUM_ARTWORK", True):
            return # Album has artwork already
        rb_artwork = ArtworkResolver(self.rb_item.tracks).resolve()
        if not rb_artwork:
            return  # Could not resolve artwork
        artwork_track, artwork_path = rb_artwork
        self.did_update = True
        logger.debug(
            f'Uploading poster "{artwork_path}" for album "{self.plex_album.title}" (resolved from track "{artwork_track.title}")'
        )
        if not is_dry_run():
            self.resolved_artwork_path = artwork_path

    def transfer(self):
        if get_boolenv("MAP_ALBUM_YEAR", True):
            self.update_year()
        if get_boolenv("MAP_ALBUM_ARTWORKS", True):
            self.update_artwork()
        return self

    def save(self):
        self.plex_album.edit(**self.edits)
        if self.resolved_artwork_path:
            self.plex_album.uploadPoster(filepath=self.resolved_artwork_path)
        self.plex_album.reload()
