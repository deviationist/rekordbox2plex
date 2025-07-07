from ..plex.repositories.ArtistRepository import ArtistRepository
from ..plex.repositories.AlbumRepository import AlbumRepository
from ..plex.data_types import PlexTrackWrapper
from ..rekordbox.data_types import ResolvedTrack
from .logger import logger
from typing import Any

class TrackMetadataMapper:
    FORCE_UPDATE = True
    def __init__(self, plex_track: PlexTrackWrapper, rb_item: ResolvedTrack):
        self.rb_item = rb_item
        self.plex_track = plex_track
        self.album_artist_rating_key = None
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
        album_artist_name = self.rb_item.album_artist.name if self.rb_item.album_artist else ""
        track_title = self.get_track_title()
        if album_artist_name:
            artist = ArtistRepository().search_for_artist(album_artist_name)
            if artist:
                logger.debug(f'Updating album artist to "{album_artist_name}" ({artist.ratingKey}) for track {track_title}')
                self.album_artist_rating_key = artist.ratingKey
                self.edits["artist.id.value"] = artist.ratingKey
                return
        logger.debug(f'Setting album artist to "{album_artist_name}" for track {track_title}')
        self.edits["artist.title.value"] = album_artist_name

    def update_album(self):
        album_name = self.rb_item.album.name if self.rb_item.album else ""
        track_title = self.get_track_title()

        # Update album assignment
        if album_name and self.album_artist_rating_key:
            album = AlbumRepository().search_for_album_by_artist(self.album_artist_rating_key, album_name)
            if album:
                self.edits["album.id.value"] = album.ratingKey
                logger.debug(f'Assigning album "{album.title}" ({album.ratingKey}) to track {track_title}')
                return

        # Create new album
        self.edits["album.title.value"] = album_name
        logger.debug(f'Creating new album {album_name} for track {track_title}')

    def transfer(self):
        self.update_track_title()
        self.update_track_artist()
        self.update_album_artist()
        self.update_album()
        return self

    def save(self):
        self.plex_track.track_object.edit(**self.edits)
        self.plex_track.track_object.reload()
