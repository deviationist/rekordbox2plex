from ..plex.repositories.TrackRepository import TrackRepository
from ..plex.data_types import PlexTrackWrapper
from ..rekordbox.resolvers.track import resolve_track as resolve_track_in_rekordbox
from ..rekordbox.data_types import ResolvedTrack
from ..mappers.TrackMetadataMapper import TrackMetadataMapper
from ..utils.progress_bar import progress_instance
from ..utils.logger import logger
from ..mappers.TrackIdMapper import TrackIdMapper
from ..utils.helpers import build_track_string
from typing import List, Tuple
from ._ActionBase import ActionBase


class TrackSync(ActionBase):
    def __init__(self):
        super().__init__("Track sync")
        self.trackIdMapper = TrackIdMapper()

    def sync(self):
        logger.info(
            "[cyan]Attempting to synchronize Rekordbox track metadata to Plex..."
        )
        plex_tracks, track_count = TrackRepository().progress(True).get_all_tracks()
        resolved_tracks, orphaned_tracks, resolved_track_count = (
            self.resolve_tracks_in_rekordbox(plex_tracks, track_count)
        )
        self.update_tracks_metadata_in_plex(resolved_tracks, resolved_track_count)
        logger.info(
            "[bold green]✔ Process complete! Rekordbox and Plex metadata should now be in sync!"
        )
        self.delete_orphaned_tracks(orphaned_tracks)

    def resolve_tracks_in_rekordbox(
        self, plex_tracks: List[PlexTrackWrapper], track_count: int
    ) -> Tuple[
        List[Tuple[PlexTrackWrapper, ResolvedTrack]], List[PlexTrackWrapper], int
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
        return resolved_tracks, orphaned_tracks, track_count

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

    def delete_orphaned_tracks(self, orphaned_tracks: List[PlexTrackWrapper]):
        """Delete tracks that are present in Plex but not in Rekordbox"""
        orphaned_tracks_count = len(orphaned_tracks)
        if orphaned_tracks_count > 0:
            logger.info(
                f"[cyan]Found {orphaned_tracks_count} orphaned track(s), deleting..."
            )
            for plex_track in orphaned_tracks:
                logger.debug(f'Delete track "{plex_track.title}"')
                if not self.dry_run:
                    plex_track.track_object.delete()
            logger.info(
                f"[bold green]✔ {orphaned_tracks_count} orphaned track(s) deleted!"
            )
