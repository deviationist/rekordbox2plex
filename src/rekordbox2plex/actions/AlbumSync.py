from ..plex.repositories.AlbumRepository import AlbumRepository as PlexAlbumRepository
from ..plex.repositories.ArtistRepository import get_artist
from ..plex.data_types import PlexAlbum, PlexAlbums, PlexArtist
from ..rekordbox.data_types import ResolvedAlbumWithTracks
from .. import config
from ..mappers.AlbumMetadataMapper import AlbumMetadataMapper
from ..rekordbox.resolvers.album import (
    get_album_with_tracks_by_album_artist,
    get_album_with_tracks_by_album_track_artists,
)
from ..utils.progress_bar import progress_instance
from ..utils.logger import logger
from ..utils.helpers import progress_count
from ._ActionBase import ActionBase
from typing import List, Literal


class AlbumSync(ActionBase):
    def __init__(self) -> None:
        super().__init__("Album sync")
        self.update_count = 0
        self.orphaned_albums: List[PlexAlbum] = []

    def sync(self):
        logger.info(
            "[cyan]Attempting to synchronize Rekordbox album metadata to Plex..."
        )
        plex_albums = PlexAlbumRepository().get_all_albums()
        album_count = len(plex_albums)
        if album_count == 0:
            logger.info("[cyan]No albums in Plex.")
            return
        else:
            logger.info(
                f"[cyan]Found {album_count} albums in Plex, proceeding to sync."
            )
            self.synchronize_albums(album_count, plex_albums)
        logger.info(f"[bold green]✔ Result: {self.update_count} albums updated.")
        if config.should_delete_orphaned_albums():
            self.delete_orphaned_albums()
        logger.info(
            "[bold green]✔ Process complete! Rekordbox and Plex albums should now be in sync!"
        )

    def resolve_album_with_tracks_using_album_artist(
        self, plex_album: PlexAlbum, plex_album_artist: PlexArtist
    ) -> ResolvedAlbumWithTracks | Literal[False]:
        lookup = get_album_with_tracks_by_album_artist(
            plex_album.title, plex_album_artist.title
        )
        if lookup:
            return lookup
        return False

    def resolve_album_with_tracks_using_album_tracks_artists(
        self, plex_album: PlexAlbum
    ) -> ResolvedAlbumWithTracks | Literal[False]:
        lookup = get_album_with_tracks_by_album_track_artists(plex_album)
        if lookup:
            return lookup
        return False

    def handle_resolved_album(
        self, plex_album: PlexAlbum, lookup: ResolvedAlbumWithTracks
    ):
        updater = AlbumMetadataMapper(plex_album, lookup).transfer()
        if not self.dry_run:
            updater.save()
        if updater.did_change:
            self.update_count += 1

    def synchronize_albums(self, plex_album_count: int, plex_albums: PlexAlbums):
        with progress_instance() as progress:
            task = progress.add_task("", total=plex_album_count)
            for i, plex_album in enumerate(plex_albums):
                count_string = progress_count(i, plex_album_count)
                if plex_album.title:
                    progress.update(
                        task,
                        description=f'[cyan]({count_string}) Processing album "{plex_album.title}"...',
                    )
                    plex_album_artist_id = plex_album.parentRatingKey
                    logger.debug(
                        f'Attempting to resolve artist with ID "{plex_album_artist_id}"'
                    )
                    plex_album_artist = get_artist(plex_album_artist_id)
                    if plex_album_artist:
                        logger.debug(
                            f'Resolved artist "{plex_album_artist.title}" from ID "{plex_album_artist_id}"'
                        )
                        logger.debug(
                            f'Attempting to resolve the Rekordbox tracks for album "{plex_album.title}" with album artist "{plex_album_artist.title}"...'
                        )

                        if lookup_by_album_artist := self.resolve_album_with_tracks_using_album_artist(
                            plex_album, plex_album_artist
                        ):
                            logger.debug(
                                f'Album "{plex_album.title}" was resolved in Rekordbox using the album artist "{plex_album_artist.title}"'
                            )
                            self.handle_resolved_album(
                                plex_album, lookup_by_album_artist
                            )  # We found the corresponding Rekordbox album using album name and album artist
                        elif lookup_by_album_track_artists := self.resolve_album_with_tracks_using_album_tracks_artists(
                            plex_album
                        ):
                            logger.debug(
                                f'Album "{plex_album.title}" was resolved in Rekordbox using one of the track artists on the existing tracks in the plex album."'
                            )
                            self.handle_resolved_album(
                                plex_album, lookup_by_album_track_artists
                            )  # We found the corresponding Rekordbox album using album name and track artist name(s)
                        else:
                            self.orphaned_albums.append(plex_album)
                            logger.debug(
                                f'Could not resolve any Rekordbox tracks for album "{plex_album.title}"...'
                            )
                    else:
                        logger.debug(
                            f'Could not resolve artist with ID "{plex_album_artist_id}"'
                        )

                    progress.update(
                        task,
                        advance=1,
                        description=f'[cyan]({count_string}) Processed album "{plex_album.title}"...',
                    )
                else:
                    progress.update(task, advance=1)
            progress.update(
                task,
                description=f"[bold green]({count_string}) ✔ Done! {plex_album_count} Rekordbox albums are synchronized with Plex!",
            )

    def delete_orphaned_albums(self):
        """Delete albums that are present in Plex but not in Rekordbox"""
        orphaned_albums_count = len(self.orphaned_albums)
        if orphaned_albums_count > 0:
            logger.info(
                f"[cyan]Found {orphaned_albums_count} orphaned album(s), deleting..."
            )
            for plex_album in self.orphaned_albums:
                logger.debug(f'Delete album "{plex_album.title}"')
                if not self.dry_run:
                    plex_album.delete()
            logger.info(
                f"[bold green]✔ {orphaned_albums_count} orphaned album(s) deleted!"
            )
