from ..plex.repositories.ArtistRepository import (
    ArtistRepository as PlexArtistRepository,
)
from ..plex.repositories.AlbumRepository import AlbumRepository as PlexAlbumRepository
from ..plex.resolvers.track import update_track_poster, get_track_thumb_file
from ..plex.data_types import PlexTrackWrapper
from ..rekordbox.data_types import ResolvedTrack
from ..utils.logger import logger
from ..utils.helpers import get_boolenv, field_is_locked
from ..utils.ArtworkResolver import ArtworkResolver
from ..utils.ImageHashComparer import ImageHashComparer
from ._MapperBase import MapperBase


class TrackMetadataMapper(MapperBase):
    def __init__(self, plex_track: PlexTrackWrapper, rb_item: ResolvedTrack):
        super().__init__()
        self.resolved_artwork_path = None
        self.rb_item = rb_item
        self.plex_track = plex_track
        self.album_artist_id = None

    def transfer(self):
        if get_boolenv("MAP_TRACK_TITLE", True):
            self.update_track_title()
        if get_boolenv("MAP_TRACK_ARTIST", True):
            self.update_track_artist()
        if get_boolenv("MAP_TRACK_ALBUM_ARTIST", True):
            self.update_album_artist()
        if get_boolenv("MAP_TRACK_ALBUM", True):
            self.update_album()
        if get_boolenv("MAP_TRACK_ARTWORK", True):
            self.update_artwork()
        return self

    def save(self):
        if not self.did_change:
            return
        if self.resolved_artwork_path:
            update_track_poster(
                self.plex_track.track_object, self.resolved_artwork_path
            )
        self.plex_track.track_object.edit(**self.edits)
        self.plex_track.track_object.reload()

    def get_track_title(self):
        return self.rb_item.track.title if self.rb_item.track else ""

    def update_track_title(self):
        rb_track_title = self.get_track_title()
        if self.plex_track.track_title != rb_track_title:
            logger.debug(f'Setting track title to "{rb_track_title}"')
            self.add_change("title.value", rb_track_title)
        if not field_is_locked(self.plex_track.track_object, "title"):
            self.add_change("title.locked", 1)

    def update_track_artist(self):
        rb_track_artist_name = self.rb_item.artist.name if self.rb_item.artist else ""
        if self.plex_track.track_artist_name != rb_track_artist_name:
            logger.debug(f'Setting track artist to "{rb_track_artist_name}"')
            self.add_change("originalTitle.value", rb_track_artist_name)
        if not field_is_locked(self.plex_track.track_object, "originalTitle"):
            self.add_change("originalTitle.locked", 1)

    def update_album_artist(self):
        rb_album_artist_name = (
            self.rb_item.album_artist.name if self.rb_item.album_artist else ""
        )
        current_album_artist_id = self.plex_track.album_artist_id
        current_album_artist_name = self.plex_track.album_artist_name

        if not rb_album_artist_name:
            return

        plex_artist = PlexArtistRepository().search_for_artist(rb_album_artist_name)

        if plex_artist:
            if plex_artist.ratingKey != current_album_artist_id:
                self.album_artist_id = plex_artist.ratingKey
                self.add_change("artist.id.value", plex_artist.ratingKey)
        else:
            if (
                rb_album_artist_name.strip().lower()
                != (current_album_artist_name or "").strip().lower()
            ):
                self.add_change("artist.title.value", rb_album_artist_name)

        if not field_is_locked(self.plex_track.track_object, "artist"):
            self.add_change("artist.locked", 1)

    def update_album(self):
        rb_album_name = self.rb_item.album.name if self.rb_item.album else ""
        current_album_id = self.plex_track.album_id
        current_album_name = self.plex_track.album_name

        if not rb_album_name:
            return

        if self.album_artist_id:
            plex_album = PlexAlbumRepository().search_for_album_by_artist(
                self.album_artist_id, rb_album_name
            )
            if plex_album and plex_album.ratingKey != current_album_id:
                self.add_change("album.id.value", plex_album.ratingKey)
        else:
            if (
                rb_album_name.strip().lower()
                != (current_album_name or "").strip().lower()
            ):
                self.add_change("album.title.value", rb_album_name)

        if not field_is_locked(self.plex_track.track_object, "album"):
            self.add_change("album.locked", 1)

    def artworks_are_the_same(self, artwork_path: str, threshold: int = 5) -> bool:
        """
        Compare the current artwork with the new artwork path.
        Returns True if they are the same, False otherwise.
        """
        existing_artwork_byte_stream = get_track_thumb_file(
            self.plex_track.track_object
        )
        if not existing_artwork_byte_stream:
            return False
        similarity, distance = ImageHashComparer().exec(
            existing_artwork_byte_stream, artwork_path, threshold
        )
        logger.debug(f"Artwork similarity: {similarity} (distance: {distance})")
        return similarity

    def update_artwork(self):
        if self.plex_track.has_artwork and not get_boolenv(
            "OVERWRITE_EXISTING_TRACK_ARTWORK", True
        ):
            logger.debug(
                "Artwork already exists for this track, skipping artwork update"
            )
            return
        artwork_path = self.rb_item.track.artwork_local_path
        if not artwork_path:
            logger.debug("No artwork path found, skipping artwork update")
            return

        filepath = ArtworkResolver().replace_rekordbox_root(artwork_path)
        if filepath:
            if not field_is_locked(self.plex_track.track_object, "thumb"):
                self.add_change("thumb.locked", 1)
            if self.artworks_are_the_same(filepath):
                logger.debug("Artwork is the same, skipping update")
                return
            track_title = self.get_track_title()
            logger.debug(f"Updating track artwork for track {track_title}")
            self.resolved_artwork_path = filepath
