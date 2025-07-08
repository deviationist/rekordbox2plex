from ..rekordbox.resolvers.playlist import (
    get_all_playlists as get_all_playlists_from_rekordbox,
    get_playlist_tracks,
)
from ..rekordbox.data_types import Playlist as RekordboxPlaylist
from ..plex.repositories.PlaylistRepository import PlaylistRepository
from ..plex.data_types import Track, PlexPlaylist, PlexPlaylists
from ..mappers.TrackIdMapper import TrackIdMapper
from ..utils.progress_bar import progress_instance
from ..utils.logger import logger
from typing import List, Literal
from ._ActionBase import ActionBase


class PlaylistSync(ActionBase):
    def __init__(self):
        super().__init__("Playlist sync")
        self.trackIdMapper = TrackIdMapper()
        self.deleted = 0
        self.created = 0
        self.updated = 0

    def sync(self) -> None:
        logger.info("[cyan]Attempting to synchronize Rekordbox playlists to Plex...")
        self.trackIdMapper.ensure_mappings()  # Ensure we have all tracks
        rb_playlists = get_all_playlists_from_rekordbox()
        if rb_playlists is False or (rb_playlists_count := len(rb_playlists)) == 0:
            logger.info("[cyan]No playlists in Rekordbox.")
        else:
            plex_playlists = PlaylistRepository().get_all_playlists()
            logger.info(
                f"[cyan]Found {len(rb_playlists)} playlists in Rekordbox, and {len(plex_playlists)} playlists in Plex, proceeding to sync them."
            )
            with progress_instance() as progress:
                task = progress.add_task("", total=rb_playlists_count)
                for rb_playlist in rb_playlists:
                    progress.update(
                        task,
                        description=f'[yellow]Synchronizing Rekordbox playlist "{rb_playlist.name}"...',
                    )
                    plex_playlist = next(
                        (pl for pl in plex_playlists if pl.title == rb_playlist.name),
                        None,
                    )
                    if plex_playlist:
                        playlist_was_synced = self.sync_playlist_tracks(
                            rb_playlist, plex_playlist
                        )  # Make sure tracks are up to date
                        if playlist_was_synced:
                            progress.update(
                                task,
                                advance=1,
                                description=f"[bold green]✔ Done! Playlist {rb_playlist.name} synchronized!",
                            )
                        else:
                            logger.debug(
                                f'Playlist "{rb_playlist.name}" already up to date.'
                            )
                            progress.update(task, advance=1)  # No Change
                    else:
                        track_count = self.create_playlist(rb_playlist)
                        if isinstance(track_count, int):
                            progress.update(
                                task,
                                advance=1,
                                description=f"[bold green]✔ Done! Playlist {rb_playlist.name} created with {track_count} tracks!",
                            )
                        else:
                            logger.debug(
                                f'Playlist "{rb_playlist.name}" not created since it is empty.'
                            )
                            progress.update(
                                task, advance=1
                            )  # Playlist not crated (most likely empty/no tracks inside)
                progress.update(
                    task,
                    description="[bold green]✔ Done! Rekordbox playlists are synchronized with Plex!",
                )
        self.delete_orphaned_playlists(rb_playlists or [], plex_playlists)
        logger.info(
            f"[bold green]✔ Result: {self.deleted} deleted, {self.updated} updated, and {self.created} created."
        )
        logger.info(
            "[bold green]✔ Process complete! Rekordbox and Plex playlists should now be in sync!"
        )

    def resolve_plex_tracks_from_rb_playlist(
        self, rb_playlist: RekordboxPlaylist
    ) -> List[Track]:
        plex_items: List[Track] = []
        rb_playlist_items = get_playlist_tracks(rb_playlist.id)
        if rb_playlist_items:
            for rb_playlist_item in rb_playlist_items:
                plex_item = self.trackIdMapper.resolve_plex_track_by_rb(
                    rb_playlist_item.id
                )
                if plex_item:
                    plex_items.append(plex_item.track_object)
        return plex_items

    def create_playlist(self, rb_playlist: RekordboxPlaylist) -> int | Literal[False]:
        plex_items = self.resolve_plex_tracks_from_rb_playlist(rb_playlist)
        track_count = len(plex_items)
        if track_count > 0:
            self.created += 1
            logger.debug(
                f'Creating playlist "{rb_playlist.name}" with {track_count} tracks'
            )
            PlaylistRepository().create_playlist(rb_playlist.name, plex_items)
            return track_count
        return False

    def add_items_to_playlist(
        self,
        plex_playlist_items_from_rb: List[Track],
        plex_playlist_existing_items: List[Track],
        plex_playlist: PlexPlaylist,
    ) -> bool:
        items_to_add = []
        for plex_item in plex_playlist_items_from_rb:
            in_playlist = self.exists_in_playlist(
                plex_item, plex_playlist_existing_items
            )
            if not in_playlist:
                items_to_add.append(plex_item)
        if len(items_to_add) > 0:
            if not self.dry_run:
                plex_playlist.addItems(items_to_add)
            return True
        return False

    def remove_items_from_playlist(
        self,
        plex_playlist_items_from_rb: List[Track],
        plex_playlist_existing_items: List[Track],
        plex_playlist: PlexPlaylist,
    ) -> bool:
        items_to_remove = []
        for plex_item in plex_playlist_existing_items:
            in_playlist = self.exists_in_playlist(
                plex_item, plex_playlist_items_from_rb
            )
            if not in_playlist:
                items_to_remove.append(plex_item)
        if len(items_to_remove) > 0:
            if not self.dry_run:
                plex_playlist.removeItems(items_to_remove)
            return True
        return False

    def exists_in_playlist(self, plex_item: Track, existing_items: List[Track]):
        return next(
            (pl for pl in existing_items if pl.ratingKey == plex_item.ratingKey),
            None,
        )

    def resolve_playlist_tracks(self, plex_playlist: PlexPlaylist) -> List[Track]:
        return plex_playlist.items()

    def sync_playlist_tracks(
        self, rb_playlist, plex_playlist: PlexPlaylist
    ) -> str | bool:
        plex_playlist_items_from_rb = self.resolve_plex_tracks_from_rb_playlist(
            rb_playlist
        )
        plex_playlist_existing_items = self.resolve_playlist_tracks(plex_playlist)
        plex_playlist_existing_item_count = len(plex_playlist_existing_items)
        if plex_playlist_existing_item_count > 0:
            did_add_items = self.add_items_to_playlist(
                plex_playlist_items_from_rb, plex_playlist_existing_items, plex_playlist
            )
            did_remove_items = self.remove_items_from_playlist(
                plex_playlist_items_from_rb, plex_playlist_existing_items, plex_playlist
            )
            if did_add_items or did_remove_items:
                self.updated += 1
                return True
            else:
                return False
        else:
            plex_playlist.delete()
            self.deleted += 1
            return False

    def delete_orphaned_playlists(
        self, rb_playlists: List[RekordboxPlaylist], plex_playlists: PlexPlaylists
    ):
        orphaned_playlists = []
        for plex_playlist in plex_playlists:
            playlist_exists_in_rb = next(
                (pl for pl in rb_playlists if pl.name == plex_playlist.title), None
            )
            if not playlist_exists_in_rb:
                orphaned_playlists.append(plex_playlist)
        orphaned_playlists_count = len(orphaned_playlists)
        if orphaned_playlists_count > 0:
            logger.info(
                f"[cyan]Found {orphaned_playlists_count} orphaned playlist(s), deleting..."
            )
            for orphaned_playlist in orphaned_playlists:
                logger.debug(f'Delete playlist "{orphaned_playlist.title}"')
                if not self.dry_run:
                    orphaned_playlist.delete()
                self.deleted += 1
            logger.info(
                f"[bold green]✔{orphaned_playlists_count} orphaned playlist(s) deleted!"
            )
