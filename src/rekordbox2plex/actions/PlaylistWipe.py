from ..plex.repositories.PlaylistRepository import (
    PlaylistRepository as PlexPlaylistRepository,
)
from ..utils.logger import logger
from ._ActionBase import ActionBase


class PlaylistWipe(ActionBase):
    def __init__(self):
        super().__init__("Playlist wipe")
        self.delete_count = 0

    def wipe(self) -> None:
        logger.info(
            "[cyan]Attempting to wipe all playlists in Plex..."
        )

        plex_playlists = PlexPlaylistRepository().get_all_playlists()
        for plex_playlist in plex_playlists:
            logger.debug(f'[cyan]Deleting playlist "{plex_playlist.title}" from Plex')
            if not self.dry_run:
                plex_playlist.delete()
        logger.info(
            f"[bold green]✔ Process complete! Deleted {len(plex_playlists)} playlists from Plex!"
        )
