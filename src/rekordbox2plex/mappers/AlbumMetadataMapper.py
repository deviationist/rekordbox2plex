from ..utils.logger import logger, print_debug_hr
from ..utils.helpers import (
    get_boolenv,
    field_is_locked,
    should_lock_fields,
    is_valid_date,
)
from typing import Literal
from ..rekordbox.data_types import ResolvedAlbumWithTracks
from ..plex.data_types import Album
from ..utils.AlbumArtworkResolver import AlbumArtworkResolver
from ._MapperBase import MapperBase


class AlbumMetadataMapper(MapperBase):
    def __init__(self, plex_album: Album, rb_lookup: ResolvedAlbumWithTracks):
        super().__init__()
        self.resolved_artwork_path = None
        self.rb_item = rb_lookup
        self.plex_album = plex_album

    def transfer(self):
        logger.debug(f'Mapping metadata for album "{self.plex_album.title}"')
        self.ensure_locked_fields()
        if get_boolenv("MAP_ALBUM_RELEASE_YEAR", True):
            self.update_release_year()
        if get_boolenv("MAP_ALBUM_RELEASE_DATE", True):
            self.update_release_date()
        if get_boolenv("MAP_ALBUM_LABEL", True):
            self.update_label()
        if get_boolenv("MAP_ALBUM_ARTWORKS", True):
            self.update_artwork()
        return self

    def save(self):
        if not self.did_change:
            return
        if self.resolved_artwork_path:
            self.plex_album.uploadPoster(filepath=self.resolved_artwork_path)
        self.plex_album.edit(**self.edits)
        self.plex_album.reload()

    def ensure_locked_fields(self) -> None:
        if not should_lock_fields():
            return
        if get_boolenv("LOCK_ALBUM_TITLE", True) and not field_is_locked(
            self.plex_album, "title"
        ):
            self.add_change("title.locked", 1)
        if get_boolenv("LOCK_ALBUM_SORT_TITLE", True) and not field_is_locked(
            self.plex_album, "titleSort"
        ):
            self.add_change("titleSort.locked", 1)

    def resolve_release_year(self) -> Literal[False] | int:
        years: list[int] = []
        for track in self.rb_item.tracks:
            if track.release_year:
                years.append(track.release_year)
        years = list(set(years))
        unique_count = len(years)
        if unique_count == 1:
            return int(years[0])
        return False

    def update_release_year(self):
        print_debug_hr()
        logger.debug("[UPDATE RELEASE YEAR]")
        rb_release_year = self.resolve_release_year()
        if rb_release_year and rb_release_year != self.plex_album.year:
            self.add_change("year.value", rb_release_year)
            logger.debug(
                f'Setting album release year to "{rb_release_year}" for album "{self.plex_album.title}"'
            )
        if (
            get_boolenv("LOCK_ALBUM_YEAR", True)
            and should_lock_fields()
            and not field_is_locked(self.plex_album, "year")
        ):
            self.add_change("year.locked", 1)

    def resolve_release_date(self) -> Literal[False] | str:
        dates: list[str] = []
        for track in self.rb_item.tracks:
            if track.release_date and is_valid_date(track.release_date):
                dates.append(track.release_date)
        dates = list(set(dates))
        unique_count = len(dates)
        if unique_count == 1:
            return dates[0]
        return False

    def update_release_date(self):
        print_debug_hr()
        logger.debug("[UPDATE RELEASE DATE]")
        rb_release_date = self.resolve_release_date()
        if (
            rb_release_date
            and is_valid_date(rb_release_date)
            and rb_release_date != self.plex_album.originallyAvailableAt
        ):
            self.add_change("originallyAvailableAt.value", rb_release_date)
            logger.debug(
                f'Setting album release date to "{rb_release_date}" for album "{self.plex_album.title}"'
            )
        if (
            get_boolenv("LOCK_ALBUM_DATE", True)
            and should_lock_fields()
            and not field_is_locked(self.plex_album, "originallyAvailableAt")
        ):
            self.add_change("originallyAvailableAt.locked", 1)

    def resolve_label(self) -> Literal[False] | str:
        labels = []
        for track in self.rb_item.tracks:
            if track.label:
                labels.append(track.label)
        labels = list(set(labels))
        unique_count = len(labels)
        if unique_count == 1:
            return labels[0]
        return False

    def update_label(self):
        print_debug_hr()
        logger.debug("[UPDATE LABEL]")
        rb_label = self.resolve_label()
        if rb_label and rb_label != self.plex_album.studio:
            self.add_change("studio.value", rb_label)
            logger.debug(
                f'Setting album label to "{rb_label}" for album "{self.plex_album.title}"'
            )
        if (
            get_boolenv("LOCK_ALBUM_LABEL", True)
            and should_lock_fields()
            and not field_is_locked(self.plex_album, "studio")
        ):
            self.add_change("studio.locked", 1)

    def update_artwork(self):
        print_debug_hr()
        logger.debug("[UPDATE ARTWORK]")
        has_thumb = bool(self.plex_album.thumb)
        if has_thumb and not get_boolenv("OVERWRITE_EXISTING_ALBUM_ARTWORK", True):
            return  # Album has artwork already
        artwork_resolver = AlbumArtworkResolver(self.rb_item.tracks).resolve()
        if not artwork_resolver:
            return  # Could not resolve artwork
        rb_artwork, exact_match = artwork_resolver

        should_update = (
            exact_match or has_thumb
        )  # Update either if we found an exact match, or if there's not artwork in Plex
        if not should_update:
            return

        artwork_track, artwork_path = rb_artwork
        self.did_change = True
        logger.debug(
            f'Uploading poster "{artwork_path}" for album "{self.plex_album.title}" (resolved from track "{artwork_track.title}")'
        )
        self.resolved_artwork_path = artwork_path

        if (
            get_boolenv("LOCK_ALBUM_ARTWORK", True)
            and should_lock_fields()
            and not field_is_locked(self.plex_album, "thumb")
        ):
            self.add_change("thumb.locked", 1)
