from ..plex.repositories.AlbumRepository import AlbumRepository
from ..plex.repositories.ArtistRepository import get_artist
from ..utils.AlbumMetadataMapper import AlbumMetadataMapper
from ..rekordbox.resolvers.album import get_album_with_tracks
from ..utils.progress_bar import progress_instance
from ..utils.logger import logger

class AlbumSync:
    def __init__(self, args):
        self.dry_run = args.dry_run

    def sync(self):
        if self.dry_run:
            logger.info("[cyan]This is a dry run! No changes will be made!")
        plex_albums = AlbumRepository().get_all_albums()
        album_count = len(plex_albums)
        with progress_instance() as progress:
            task = progress.add_task("", total=album_count)
            for plex_album in plex_albums:
                if plex_album.title:
                    progress.update(task, description=f'[yellow]Procesing album {plex_album.title}...')
                    album_artist_id = plex_album.parentRatingKey
                    artist = get_artist(album_artist_id)
                    if artist:
                        lookup = get_album_with_tracks(plex_album.title, artist.title)
                        if lookup:
                            updater = AlbumMetadataMapper(plex_album, lookup).transfer()
                            if not self.dry_run:
                                updater.save()
                    progress.update(task, advance=1, description=f'[yellow]Procesed album {plex_album.title}...')
                else:
                    progress.update(task, advance=1)
