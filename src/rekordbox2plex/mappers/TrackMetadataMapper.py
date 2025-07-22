from ..plex.repositories.ArtistRepository import (
    ArtistRepository as PlexArtistRepository,
)
from ..plex.repositories.AlbumRepository import AlbumRepository as PlexAlbumRepository
from ..plex.resolvers.track import update_track_poster, get_track_thumb_file
from ..plex.data_types import PlexTrackWrapper, PlexArtist, PlexAlbum
from ..rekordbox.data_types import ResolvedTrack
from ..utils.logger import logger
from ..utils.helpers import get_boolenv, field_is_locked, should_lock_fields
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
        self.album_artist_did_change = False
        self.album_did_change = False
        self._track_title: str | None = None
        self._track_artist_name: str | None = None
        self._album_artist_name: str | None = None
        self._album_name: str | None = None

    def transfer(self):
        logger.debug(f'Mapping metadata for track "{self.get_track_title()}"')
        if get_boolenv("MAP_TRACK_TITLE", True):
            self.update_track_title()
        if get_boolenv("MAP_TRACK_ARTIST", True):
            self.update_track_artist()
        if get_boolenv("MAP_TRACK_ALBUM", True):
            self.handle_album_metadata()
        if get_boolenv("MAP_TRACK_ARTWORK", True):
            self.update_artwork()
        return self

    def save(self):
        if not self.did_change:
            return

        # Reparenting update
        reparent_keys = {
            "artist.id.value",
            "artist.title.value",
            "album.id.value",
            "album.title.value",
        }
        reparent_edits = {k: v for k, v in self.edits.items() if k in reparent_keys}

        if reparent_edits:
            logger.debug(f"Applying reparenting edits: {reparent_edits}")
            try:
                self.plex_track.track_object.edit(**reparent_edits)
            except Exception as e:
                logger.warning(f"Failed to apply reparenting metadata: {e}")

        # Apply artwork
        if self.resolved_artwork_path:
            update_track_poster(
                self.plex_track.track_object, self.resolved_artwork_path
            )

        # Remaining metadata
        remaining_edits = {
            k: v for k, v in self.edits.items() if k not in reparent_keys
        }
        if remaining_edits:
            logger.debug(f"Applying remaining edits: {remaining_edits}")
            try:
                self.plex_track.track_object.edit(**remaining_edits)
            except Exception as e:
                logger.warning(f"Failed to apply remaining metadata: {e}")

        # Reload track object if needed
        if reparent_edits or remaining_edits or self.resolved_artwork_path:
            self.plex_track.track_object.reload()

    def handle_album_metadata(self):
        logger.debug("[HANDLE ALBUM METADATA]")
        self.update_album_artist()
        self.update_album(self.album_artist_did_change)  # Maybe force album update
        if self.album_did_change and not self.album_artist_did_change:
            self.update_album_artist(
                True
            )  # Force album artist to be part of payload since album was changed

    # --- Track Title ---
    def get_track_title(self):
        if not self._track_title:
            self._track_title = self.rb_item.track.title if self.rb_item.track else ""
        return self._track_title

    def update_track_title(self):
        logger.debug("[UPDATE TRACK TITLE]")
        rb_track_title = self.get_track_title()
        if self.plex_track.track_title != rb_track_title:  # Check for changes
            logger.debug(f'Setting track title to "{rb_track_title}"')
            self.add_change("title.value", rb_track_title)
        else:
            logger.debug(f'Track title already set to "{rb_track_title}"')
        if get_boolenv("LOCK_TRACK_TITLE", True) and should_lock_fields() and not field_is_locked(self.plex_track.track_object, "title"):
            logger.debug(f'Locking track title for "{rb_track_title}"')
            self.add_change("title.locked", 1)

    # --- Track Artist ---
    def update_track_artist(self):
        logger.debug("[UPDATE TRACK ARTIST]")
        rb_track_artist_name = self.get_track_artist_name()
        rb_track_title = self.get_track_title()
        if (
            self.plex_track.track_artist_name != rb_track_artist_name
        ):  # Check for changes
            logger.debug(
                f'Setting track artist to "{rb_track_artist_name}" for track "{rb_track_title}"'
            )
            self.add_change("originalTitle.value", rb_track_artist_name)
        else:
            logger.debug(f'Track artist already set to "{rb_track_artist_name}"')
        self.ensure_track_artist_locked()

    def get_track_artist_name(self) -> str:
        if not self._track_artist_name:
            self._track_artist_name = (
                self.rb_item.artist.name if self.rb_item.artist else ""
            )
        return self._track_artist_name

    def ensure_track_artist_locked(self):
        if get_boolenv("LOCK_TRACK_ARTIST", True) and should_lock_fields() and not field_is_locked(self.plex_track.track_object, "originalTitle"):
            logger.debug(
                f'Locking track artist for "{self.get_track_artist_name()}" for track "{self.get_track_title()}"'
            )
            self.add_change("originalTitle.locked", 1)

    # --- Album Artist ---
    def update_album_artist(self, force_creation: bool = False):
        logger.debug("[UPDATE ALBUM ARTIST]")
        rb_album_artist_name = self.get_album_artist_name()
        rb_track_title = self.get_track_title()
        plex_album_artist_id = self.plex_track.album_artist_id
        plex_album_artist_name = self.plex_track.album_artist_name

        #logger.debug(
        #    f'Current album artist "{plex_album_artist_name}" (ID "{plex_album_artist_id}") for track "{rb_track_title}"'
        #)
        logger.debug(f'RB Track: "{rb_track_title}" by "{rb_album_artist_name}"')
        logger.debug(f'Plex Track: "{self.plex_track.track_title}" by "{plex_album_artist_name}"')

        if not rb_album_artist_name:
            return
        if force_creation:
            logger.debug("Forcing artist creation by sending album album name")
            self.update_album_artist_with_name(
                True
            )  # Force update payload, create new album artist
        else:
            logger.debug(f'Searching for Plex artist by search string "{rb_album_artist_name}"')
            plex_artist = PlexArtistRepository().search_for_artist(rb_album_artist_name)
            if plex_artist:
                logger.debug(f'Resolved Plex artist "{plex_artist.title}" (ID "{plex_artist.ratingKey}")')
                self.update_album_artist_with_id(
                    plex_artist
                )  # Assign existing album artist
            else:
                logger.debug(f'Could not resolve Plex artist by search string "{rb_album_artist_name}"')
                self.update_album_artist_with_name()  # Create new album artist

    def update_album_artist_with_id(self, plex_artist: PlexArtist):
        rb_track_title = self.get_track_title()
        plex_album_artist_id = self.plex_track.album_artist_id
        plex_album_artist_name = self.plex_track.album_artist_name
        self.album_artist_id = plex_artist.ratingKey
        logger.debug("Attempting to update album artist ID")
        if plex_artist.ratingKey != plex_album_artist_id:  # Check for changes
            logger.debug(
                f'Setting album artist to "{plex_artist.title}" (ID "{plex_artist.ratingKey}") for track "{rb_track_title}"'
            )
            self.album_artist_did_change = True
            self.add_change("artist.id.value", plex_artist.ratingKey)
        else:
            logger.debug(
                f'Album artist already set to "{plex_album_artist_name}" (ID "{plex_album_artist_id}") for track "{rb_track_title}"'
            )

    def update_album_artist_with_name(self, force_update: bool = False):
        rb_album_artist_name = self.get_album_artist_name()
        rb_track_title = self.get_track_title()
        plex_album_artist_name = self.plex_track.album_artist_name
        if force_update or (
            rb_album_artist_name.strip().lower()
            != (plex_album_artist_name or "").strip().lower()
        ):
            logger.debug(
                f'Setting album artist to "{rb_album_artist_name}" for track "{rb_track_title}"'
            )
            self.album_artist_did_change = True
            self.add_change("artist.title.value", rb_album_artist_name)
        else:
            logger.debug(
                f'Album artist already set to "{plex_album_artist_name}" for track "{rb_track_title}"'
            )

    def get_album_artist_name(self) -> str:
        if not self._album_artist_name:
            self._album_artist_name = (
                self.rb_item.album_artist.name if self.rb_item.album_artist else ""
            )
        return self._album_artist_name

    # --- Album ---
    def update_album(self, force_creation: bool = False):
        logger.debug("[UPDATE ALBUM]")
        rb_album_name = self.get_album_name()
        rb_track_title = self.get_track_title()
        plex_album_id = self.plex_track.album_id
        plex_album_name = self.plex_track.album_name
        logger.debug(
            f'Current album "{plex_album_name}" (ID "{plex_album_id}") for track "{rb_track_title}"'
        )

        if not rb_album_name:
            return
        if force_creation:
            logger.debug("Forcing album creation by sending album name")
            self.update_album_with_name(True)
        else:
            if plex_album := self.resolve_album_id(rb_album_name):
                self.update_album_with_id(plex_album)
            else:
                self.update_album_with_name()

    def update_album_with_id(self, plex_album: PlexAlbum) -> bool:
        rb_track_title = self.get_track_title()
        plex_album_id = self.plex_track.album_id
        plex_album_name = self.plex_track.album_name
        if plex_album:
            logger.debug("Attempting to update album ID")
            if plex_album.ratingKey != plex_album_id:  # Check for changes
                self.album_did_change = True
                logger.debug(
                    f'Setting album to "{plex_album.title}" (ID "{plex_album.ratingKey}") for track "{rb_track_title}"'
                )
                self.add_change("album.id.value", plex_album.ratingKey)
            else:
                logger.debug(
                    f'Album already set to "{plex_album_name}" (ID "{plex_album_id}") for track "{rb_track_title}"'
                )
            return True
        else:
            logger.debug(
                f'Could not resolve plex album ID for track "{rb_track_title}"'
            )
            return False

    def update_album_with_name(self, force_update: bool = False):
        rb_album_name = self.get_album_name()
        rb_track_title = self.get_track_title()
        plex_album_name = self.plex_track.album_name
        logger.debug(
            "Album artist ID is not set, album artist will most likely be created when we save"
        )
        if force_update or (
            rb_album_name.strip().lower() != (plex_album_name or "").strip().lower()
        ):
            self.album_did_change = True
            logger.debug(
                f'Setting album to "{rb_album_name}" for track "{rb_track_title}"'
            )
            self.add_change("album.title.value", rb_album_name)
        else:
            logger.debug(
                f'Album already set to "{plex_album_name}" for track "{rb_track_title}"'
            )

    def resolve_album_id(self, rb_album_name: str) -> None | PlexAlbum:
        if self.album_artist_id:
            return PlexAlbumRepository().search_for_album_by_artist(
                self.album_artist_id, rb_album_name
            )
        return None

    def get_album_name(self) -> str:
        if not self._album_name:
            self._album_name = self.rb_item.album.name if self.rb_item.album else ""
        return self._album_name

    # --- Artwork ---
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
        logger.debug("[UPDATE ARTWORK]")
        rb_track_title = self.get_track_title()
        if self.plex_track.has_artwork and not get_boolenv(
            "OVERWRITE_EXISTING_TRACK_ARTWORK", True
        ):
            logger.debug(
                f'Artwork already exists for track "{rb_track_title}", skipping artwork update'
            )
            return
        artwork_path = self.rb_item.track.artwork_local_path
        if not artwork_path:
            logger.debug(
                f'No artwork path found for track "{rb_track_title}", skipping artwork update'
            )
            return

        filepath = ArtworkResolver().replace_rekordbox_root(artwork_path)
        if filepath:
            self.ensure_thumb_locked()
            if self.plex_track.has_artwork and self.artworks_are_the_same(filepath):
                logger.debug(
                    f'Artwork is the same for track "{rb_track_title}", skipping update'
                )
                return
            track_title = self.get_track_title()
            logger.debug(f'Updating track artwork for track "{track_title}"')
            self.resolved_artwork_path = filepath

    def ensure_thumb_locked(self) -> None:
        if get_boolenv("LOCK_TRACK_ARTWORK", True) and should_lock_fields() and not field_is_locked(self.plex_track.track_object, "thumb"):
            logger.debug(f'Locking thumb for track "{self.get_track_title()}"')
            self.add_change("thumb.locked", 1)
