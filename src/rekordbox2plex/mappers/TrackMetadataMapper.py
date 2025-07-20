from ..plex.repositories.ArtistRepository import ArtistRepository
from ..plex.repositories.AlbumRepository import AlbumRepository
from ..plex.resolvers.track import update_track_poster
from ..plex.data_types import PlexTrackWrapper
from ..rekordbox.data_types import ResolvedTrack
from ..utils.logger import logger
from ..utils.helpers import get_boolenv
from ..config import is_dry_run
from typing import Any
from ..utils.ArtworkResolver import ArtworkResolver


class TrackMetadataMapper:
    def __init__(self, plex_track: PlexTrackWrapper, rb_item: ResolvedTrack):
        self.dry_run = is_dry_run()
        self.rb_item = rb_item
        self.plex_track = plex_track
        self.album_artist_id = None
        self.edits: dict[str, Any] = {}

    def get_track_title(self):
        return self.rb_item.track.title if self.rb_item.track else ""

    def update_track_title(self):
        track_title = self.get_track_title()
        logger.debug(f'Setting track title to "{track_title}"')
        self.edits["title.locked"] = 1
        self.edits["title.value"] = track_title

    def update_track_artist(self):
        artist_name = self.rb_item.artist.name if self.rb_item.artist else ""
        logger.debug(f'Setting track artist to "{artist_name}"')
        self.edits["originalTitle.value"] = artist_name
        self.edits["originalTitle.locked"] = 1

    def update_album_artist(self):
        album_artist_name = (
            self.rb_item.album_artist.name if self.rb_item.album_artist else ""
        )
        track_title = self.get_track_title()
        if album_artist_name:
            artist = ArtistRepository().search_for_artist(album_artist_name)
            if artist:
                logger.debug(
                    f'Updating album artist to "{album_artist_name}" ({artist.ratingKey}) for track "{track_title}"'
                )
                self.album_artist_id = artist.ratingKey
                self.edits["artist.id.value"] = artist.ratingKey
                return
        logger.debug(
            f'Setting album artist to "{album_artist_name}" for track "{track_title}"'
        )
        self.edits["artist.title.value"] = album_artist_name

    def update_album(self):
        album_name = self.rb_item.album.name if self.rb_item.album else ""
        track_title = self.get_track_title()

        # Update album assignment
        if album_name and self.album_artist_id:
            album = AlbumRepository().search_for_album_by_artist(
                self.album_artist_id, album_name
            )
            if album:
                self.edits["album.id.value"] = album.ratingKey
                logger.debug(
                    f'Assigning album "{album.title}" ({album.ratingKey}) to track {track_title}'
                )
                return

        # Create new album
        self.edits["album.title.value"] = album_name
        logger.debug(f'Creating new album "{album_name}" for track "{track_title}"')

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
            track_title = self.get_track_title()
            logger.debug(f"Updating track artwork for track {track_title}")
            if not self.dry_run:
                update_track_poster(self.plex_track.id, filepath)

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
        self.plex_track.track_object.edit(**self.edits)
        self.plex_track.track_object.reload()
