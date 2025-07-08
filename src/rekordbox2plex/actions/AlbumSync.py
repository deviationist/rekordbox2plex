from ..plex.repositories.AlbumRepository import AlbumRepository
from ..plex.repositories.ArtistRepository import get_artist
from ..plex.data_types import PlexAlbum
from ..mappers.AlbumMetadataMapper import AlbumMetadataMapper
from ..rekordbox.resolvers.album import get_album_with_tracks
from ..utils.progress_bar import progress_instance
from ..utils.logger import logger
from ..utils.helpers import get_boolenv
from ._ActionBase import ActionBase
from typing import List


class AlbumSync(ActionBase):
    def __init__(self):
        super().__init__("Album sync")
        self.update_count = 0

    def sync(self):
        logger.info(
            "[cyan]Attempting to synchronize Rekordbox album metadata to Plex..."
        )
        plex_albums = AlbumRepository().get_all_albums()
        album_count = len(plex_albums)
        if album_count == 0:
            logger.info("[cyan]No playlists in Plex.")
            return
        else:
            logger.info(
                f"[cyan]Found {album_count} albums in Plex, proceeding to sync."
            )
        with progress_instance() as progress:
            task = progress.add_task("", total=album_count)
            orphaned_albums = []
            for plex_album in plex_albums:
                if plex_album.title:
                    progress.update(
                        task,
                        description=f'[yellow]Procesing album "{plex_album.title}"...',
                    )
                    album_artist_id = plex_album.parentRatingKey
                    artist = get_artist(album_artist_id)
                    if artist:
                        lookup = get_album_with_tracks(plex_album.title, artist.title)
                        if lookup:
                            updater = AlbumMetadataMapper(plex_album, lookup).transfer()
                            if not self.dry_run:
                                updater.save()
                            if updater.did_update:
                                self.update_count += 1
                        else:
                            orphaned_albums.append(plex_album)

                    progress.update(
                        task,
                        advance=1,
                        description=f'[yellow]Processed album "{plex_album.title}"...',
                    )
                else:
                    progress.update(task, advance=1)
            progress.update(
                task,
                description="[bold green]✔ Done! Rekordbox albums are synchronized with Plex!",
            )
        logger.info(f"[bold green]✔ Result: {self.update_count} albums updated.")
        if get_boolenv("DELETE_ORPHANED_ALBUMS", "false"):
            self.delete_orphaned_albums(orphaned_albums)
        logger.info(
            "[bold green]✔ Process complete! Rekordbox and Plex albums should now be in sync!"
        )

    def delete_orphaned_albums(self, orphaned_albums: List[PlexAlbum]):
        """Delete albums that are present in Plex but not in Rekordbox"""
        orphaned_albums_count = len(orphaned_albums)
        if orphaned_albums_count > 0:
            logger.info(
                f"[cyan]Found {orphaned_albums_count} orphaned album(s), deleting..."
            )
            for plex_album in orphaned_albums:
                logger.debug(f'Delete album "{plex_album.title}"')
                if not self.dry_run:
                    plex_album.delete()
            logger.info(
                f"[bold green]✔ {orphaned_albums_count} orphaned album(s) deleted!"
            )
