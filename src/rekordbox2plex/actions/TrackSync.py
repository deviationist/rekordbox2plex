from ..plex.repositories.TrackRepository import TrackRepository
from ..plex.data_types import PlexTrackWrapper
from ..plex.resolvers.track import convert_path_to_plex
from ..plex.resolvers.library import update_library
from ..rekordbox.resolvers.track import (
    resolve_track as resolve_track_in_rekordbox,
    get_all_tracks as get_all_tracks_in_rekordbox,
)
from .. import config
from ..rekordbox.data_types import ResolvedTrack
from ..mappers.TrackMetadataMapper import TrackMetadataMapper
from ..utils.progress_bar import progress_instance
from ..utils.logger import logger
from ..mappers.TrackIdMapper import TrackIdMapper
from ..utils.helpers import build_track_string, get_boolenv
from ._ActionBase import ActionBase
from typing import List, Tuple
import os


class TrackSync(ActionBase):
    def __init__(self):
        super().__init__("Track sync")
        self.trackIdMapper = TrackIdMapper()

    def sync(self):
        logger.info(
            "[cyan]Attempting to synchronize Rekordbox track metadata to Plex..."
        )
        plex_tracks, track_count = TrackRepository().progress(True).get_all_tracks()
        resolved_tracks, resolved_track_count, orphaned_tracks = (
            self.resolve_tracks_in_rekordbox(plex_tracks, track_count)
        )
        self.update_tracks_metadata_in_plex(resolved_tracks, resolved_track_count)
        if get_boolenv("ADD_NEW_TRACKS", "true"):
            self.add_new_tracks()
        if get_boolenv("DELETE_ORPHANED_TRACKS", "false"):
            self.delete_orphaned_tracks(orphaned_tracks)
        logger.info(
            "[bold green]✔ Process complete! Rekordbox and Plex metadata should now be in sync!"
        )

    def resolve_tracks_in_rekordbox(
        self, plex_tracks: List[PlexTrackWrapper], track_count: int
    ) -> Tuple[
        List[Tuple[PlexTrackWrapper, ResolvedTrack]], int, List[PlexTrackWrapper]
    ]:
        with progress_instance() as progress:
            logger.info("[cyan]Resolving track metadata in Rekordbox database...")
            task = progress.add_task("", total=track_count)
            resolved_tracks = []
            orphaned_tracks = []
            for plex_track in plex_tracks:
                track_string = build_track_string(plex_track)
                progress.update(
                    task,
                    description=f"[yellow]Resolving Rekordbox track metadata {track_string}...",
                )
                rb_item = resolve_track_in_rekordbox(plex_track, progress, task)
                if rb_item:
                    resolved_tracks.append((plex_track, rb_item))
                    self.trackIdMapper.map(plex_track, rb_item)
                    progress.update(
                        task,
                        advance=1,
                        description=f"[yellow]Resolved Rekordbox track metadata {track_string}...",
                    )
                else:
                    orphaned_tracks.append(
                        plex_track
                    )  # Flag track for deletion since it's not present in Rekordbox
                    progress.update(
                        task,
                        advance=1,
                        description=f"[red]Could not resolve track metadata {track_string}...",
                    )
            self.trackIdMapper.all_tracks_mapped()
            track_count = len(resolved_tracks)
            orphaned_tracks_count = len(orphaned_tracks)
            progress.update(
                task,
                description=f"[bold green]✔ Done! Resolved Rekordbox metadata for {track_count} tracks!",
            )
        if orphaned_tracks_count > 0:
            logger.info(
                f"[yellow]{orphaned_tracks_count} track(s) seems to be orphaned and will be deleted from Plex."
            )
        return resolved_tracks, track_count, orphaned_tracks

    def update_tracks_metadata_in_plex(
        self,
        resolved_tracks: List[Tuple[PlexTrackWrapper, ResolvedTrack]],
        track_count: int,
    ):
        with progress_instance() as progress:
            logger.info("[cyan]Updating track metadata in Plex...")
            task = progress.add_task("", total=track_count)
            for plex_track, rb_item in resolved_tracks:
                track_string = build_track_string(plex_track)
                progress.update(
                    task, description=f"[yellow]Processing track {track_string}..."
                )
                if rb_item:
                    updater = TrackMetadataMapper(plex_track, rb_item).transfer()
                    if not self.dry_run:
                        updater.save()
                progress.update(
                    task,
                    advance=1,
                    description=f"[yellow]Procesed track {track_string}...",
                )
            progress.update(
                task,
                description=f"[bold green]✔ Done! Updated metadata for {track_count} tracks!",
            )

    def add_new_tracks(self):
        """Get tracks that are present in Rekordbox but not in Plex and add them to Plex using library update for the folder with the tracks."""
        logger.debug(
            "[cyan]Adding new tracks from Rekordbox to Plex that are not already present..."
        )

        folders_to_ignore = config.get_folders_to_ignore()
        rb_tracks = get_all_tracks_in_rekordbox(folders_to_ignore)
        folders_to_update = []
        new_tracks_count = 0

        # Loop through Rekordbox tracks, attempt to resolve them in Plex using the mapper, if not then flag the folder as updated and add it to a list to be updated later
        for rb_track in rb_tracks:
            plex_track = self.trackIdMapper.resolve_plex_track_by_rb(rb_track.id)
            if not plex_track:
                logger.debug(
                    f"[yellow]Track {rb_track.title} not found in Plex, adding to library update list."
                )
                new_tracks_count += 1
                rb_folder_path = os.path.dirname(rb_track.folder_path)
                plex_folder_path = convert_path_to_plex(rb_folder_path)
                # Convert to Plex path
                if plex_folder_path not in folders_to_update:
                    folders_to_update.append(plex_folder_path)
                    logger.debug(
                        f"[yellow]Adding folder {plex_folder_path} to update list for new tracks."
                    )

        folders_to_update_count = len(folders_to_update)

        if folders_to_update_count == 0:
            logger.debug(
                "[green]No new tracks found in Rekordbox that are not already present in Plex."
            )
            return

        logger.info(
            f"[cyan]Found {new_tracks_count} new track(s) in {folders_to_update_count} folders, starting library re-index for these folders..."
        )

        for folder_to_update in folders_to_update:
            logger.debug(
                f"[yellow]Re-indexing folder {folder_to_update} to add new tracks."
            )
            if not self.dry_run:
                update_library(folder_to_update)
        logger.info(
            f"[bold green]✔ {folders_to_update_count} folders are added for re-indexing!"
        )

    def delete_orphaned_tracks(self, orphaned_tracks: List[PlexTrackWrapper]):
        """Delete tracks that are present in Plex but not in Rekordbox"""
        orphaned_tracks_count = len(orphaned_tracks)
        if orphaned_tracks_count > 0:
            logger.info(
                f"[cyan]Found {orphaned_tracks_count} orphaned track(s), deleting..."
            )
            for plex_track in orphaned_tracks:
                logger.debug(f'Deleting track "{plex_track.title}"')
                if not self.dry_run:
                    plex_track.track_object.delete()
            logger.info(
                f"[bold green]✔ {orphaned_tracks_count} orphaned track(s) deleted!"
            )
