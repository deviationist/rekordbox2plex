from ..plex.repositories.AlbumRepository import AlbumRepository as PlexAlbumRepository
from ..plex.repositories.ArtistRepository import get_artist
from ..plex.data_types import PlexAlbum, PlexAlbums
from ..rekordbox.data_types import ResolvedAlbumWithTracks
from ..mappers.AlbumMetadataMapper import AlbumMetadataMapper
from ..rekordbox.resolvers.album import get_album_with_tracks
from ..utils.progress_bar import progress_instance
from ..utils.logger import logger
from ..utils.helpers import get_boolenv, progress_count
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
            logger.info("[cyan]No playlists in Plex.")
            return
        else:
            logger.info(
                f"[cyan]Found {album_count} albums in Plex, proceeding to sync."
            )
            self.synchronize_albums(album_count, plex_albums)
        logger.info(f"[bold green]✔ Result: {self.update_count} albums updated.")
        if get_boolenv("DELETE_ORPHANED_ALBUMS", False):
            self.delete_orphaned_albums()
        logger.info(
            "[bold green]✔ Process complete! Rekordbox and Plex albums should now be in sync!"
        )

    def resolve_album_with_tracks(
        self, album_title: str, artist_title: str
    ) -> ResolvedAlbumWithTracks | Literal[False]:
        lookup = get_album_with_tracks(album_title, artist_title)
        if lookup:
            return lookup
        return False

    def synchronize_albums(self, plex_album_count: int, plex_albums: PlexAlbums):
        with progress_instance() as progress:
            task = progress.add_task("", total=plex_album_count)
            for i, plex_album in enumerate(plex_albums):
                count_string = progress_count(i, plex_album_count)
                if plex_album.title:
                    progress.update(
                        task,
                        description=f'[cyan]({count_string}) Procesing album "{plex_album.title}"...',
                    )
                    album_artist_id = plex_album.parentRatingKey
                    logger.debug(
                        f'Attempting to resolve artist with ID "{album_artist_id}"'
                    )
                    artist = get_artist(album_artist_id)
                    if artist:
                        logger.debug(
                            f'Resolved artist "{artist.title}" from ID "{album_artist_id}"'
                        )
                        logger.debug(
                            f'Attempting to resolve the Rekordbox tracks for album "{plex_album.title}"...'
                        )
                        lookup = self.resolve_album_with_tracks(
                            plex_album.title, artist.title
                        )
                        if lookup:
                            updater = AlbumMetadataMapper(plex_album, lookup).transfer()
                            if not self.dry_run:
                                updater.save()
                            if updater.did_change:
                                self.update_count += 1
                        else:
                            self.orphaned_albums.append(plex_album)
                            logger.debug(
                                f'Could not resolve any Rekordbox tracks for album "{plex_album.title}"...'
                            )
                    else:
                        logger.debug(
                            f'Could not resolve artist with ID "{album_artist_id}"'
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
