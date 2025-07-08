from ..plex.repositories.AlbumRepository import AlbumRepository
from ..plex.repositories.ArtistRepository import get_artist
from ..mappers.AlbumMetadataMapper import AlbumMetadataMapper
from ..rekordbox.resolvers.album import get_album_with_tracks
from ..utils.progress_bar import progress_instance
from ..utils.logger import logger
from ._ActionBase import ActionBase


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

        self.delete_orphaned_albums()
        logger.info(f"[bold green]✔ Result: {self.update_count} albums updated.")
        logger.info(
            "[bold green]✔ Process complete! Rekordbox and Plex albums should now be in sync!"
        )

    def delete_orphaned_albums(self):
        pass
