from ..plex.repositories.ArtistRepository import (
    ArtistRepository as PlexArtistRepository,
)
from ..plex.repositories.AlbumRepository import AlbumRepository as PlexAlbumRepository
from ..plex.resolvers.track import update_track_poster, get_track_thumb_file
from ..plex.data_types import PlexTrackWrapper
from ..rekordbox.data_types import ResolvedTrack
from ..utils.logger import logger
from ..utils.helpers import get_boolenv, field_is_locked
from typing import Any
from ..utils.ArtworkResolver import ArtworkResolver
from ..utils.ImageHashComparer import ImageHashComparer


class TrackMetadataMapper:
    def __init__(self, plex_track: PlexTrackWrapper, rb_item: ResolvedTrack):
        self.did_change = False
        self.resolved_artwork_path = None
        self.rb_item = rb_item
        self.plex_track = plex_track
        self.album_artist_id = None
        self.edits: dict[str, Any] = {}

    def get_track_title(self):
        return self.rb_item.track.title if self.rb_item.track else ""

    def update_track_title(self):
        rb_track_title = self.get_track_title()
        if self.plex_track.track_title != rb_track_title:
            self.did_change = True
            logger.debug(f'Setting track title to "{rb_track_title}"')
            self.edits["title.value"] = rb_track_title
        if not field_is_locked(self.plex_track, "title"):
            self.did_change = True
            self.edits["title.locked"] = 1

    def update_track_artist(self):
        rb_track_artist_name = self.rb_item.artist.name if self.rb_item.artist else ""
        if self.plex_track.track_artist_name != rb_track_artist_name:
            self.did_change = True
            logger.debug(f'Setting track artist to "{rb_track_artist_name}"')
            self.edits["originalTitle.value"] = rb_track_artist_name
        if not field_is_locked(self.plex_track, "tioriginalTitletle"):
            self.did_change = True
            self.edits["originalTitle.locked"] = 1

    def update_album_artist(self):
        rb_track_title = self.get_track_title()
        rb_album_artist_name = (
            self.rb_item.album_artist.name if self.rb_item.album_artist else ""
        )

        if rb_album_artist_name:
            plex_artist = PlexArtistRepository().search_for_artist(rb_album_artist_name)
            current_album_artist_id = self.plex_track.album_artist_id
            if plex_artist and plex_artist.ratingKey != current_album_artist_id:
                self.did_change = True
                logger.debug(
                    f'Updating album artist to "{rb_album_artist_name}" ({plex_artist.ratingKey}) for track "{rb_track_title}"'
                )
                self.album_artist_id = plex_artist.ratingKey
                self.edits["artist.id.value"] = plex_artist.ratingKey
                return

        # Create new album artist if not found
        self.did_change = True
        logger.debug(
            f'Setting album artist to "{rb_album_artist_name}" for track "{rb_track_title}"'
        )
        self.edits["artist.title.value"] = rb_album_artist_name

    def update_album(self):
        rb_album_name = self.rb_item.album.name if self.rb_item.album else ""
        rb_track_title = self.get_track_title()
        self.did_change = True

        # Update album assignment
        if rb_album_name and self.album_artist_id:
            plex_album = PlexAlbumRepository().search_for_album_by_artist(
                self.album_artist_id, rb_album_name
            )
            if plex_album:
                self.edits["album.id.value"] = plex_album.ratingKey
                logger.debug(
                    f'Assigning album "{plex_album.title}" ({plex_album.ratingKey}) to track {rb_track_title}'
                )
                return

        # Create new album
        self.edits["album.title.value"] = rb_album_name
        logger.debug(
            f'Creating new album "{rb_album_name}" for track "{rb_track_title}"'
        )

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
            if self.artworks_are_the_same(filepath):
                logger.debug("Artwork is the same, skipping update")
                return
            track_title = self.get_track_title()
            logger.debug(f"Updating track artwork for track {track_title}")
            self.resolved_artwork_path = filepath

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
        if self.did_change:
            if self.resolved_artwork_path:
                update_track_poster(
                    self.plex_track.track_object, self.resolved_artwork_path
                )
            self.plex_track.track_object.edit(**self.edits)
            self.plex_track.track_object.reload()
