from ..utils.AudioMetadataMapper import AudioMetadataMapper
from ..plex.repository.TrackRepository import TrackRepository
from ..rekordbox.track_resolver import resolve_track as resolve_track_in_rekordbox
from ..utils.progress_bar import progress_instance
from ..utils.logger import logger
from ..utils.TrackIdMapper import TrackIdMapper
from ..utils.helpers import build_track_string

class TrackSync:
    def __init__(self):
        self.trackIdMapper = TrackIdMapper()

    def sync(self):
        plex_tracks, track_count = TrackRepository().progress(True).get_all_tracks()
        resolved_tracks, resolve_track_count = self.resolve_tracks_in_rekordbox(plex_tracks, track_count)
        if resolve_track_count != track_count:
            logger.info("[red]The count between fetched tracks from Plex and resolved tracks from Rekordbox does not seem to match, there might be something fishy going on! Please re-index your Plex library and try again!")
        self.update_tracks_metadata_in_plex(resolved_tracks, resolve_track_count)
        logger.info(f"[bold green]✔ Process complete! Rekordbox and Plex metadata should now be in sync!")

    def resolve_tracks_in_rekordbox(self, plex_tracks, track_count):
        with progress_instance() as progress:
            logger.info("[cyan]Resolving track metadata in Rekordbox database...")
            task = progress.add_task("", total=track_count)
            resolved_tracks = []
            for plex_track in plex_tracks:
                track_string = build_track_string(plex_track)
                progress.update(task, description=f'[yellow]Resolving Rekordbox track metadata {track_string}...')
                rb_item = resolve_track_in_rekordbox(plex_track, progress, task)
                if rb_item:
                    resolved_tracks.append((plex_track, rb_item))
                    self.trackIdMapper.map(plex_track, rb_item)
                    progress.update(task, advance=1, description=f'[yellow]Resolved Rekordbox track metadata {track_string}...')
                else:
                    progress.update(task, advance=1, description=f'[red]Could not resolve track metadata {track_string}...')
            progress.update(task, description=f"[bold green]✔ Done! Resolved Rekordbox metadata for {track_count} tracks!")
            track_count = len(resolved_tracks)
            return resolved_tracks, track_count

    def update_tracks_metadata_in_plex(self, resolved_tracks, track_count):
        with progress_instance() as progress:
            logger.info("[cyan]Updating track metadata in Plex...")
            task = progress.add_task("", total=track_count)
            for plex_track, rb_item in resolved_tracks:
                track_string = build_track_string(plex_track)
                progress.update(task, description=f"[yellow]Processing track {track_string}...")
                if rb_item:
                    AudioMetadataMapper(plex_track, rb_item).transfer().save()
                progress.update(task, advance=1, description=f'[yellow]Procesed track {track_string}...')
            progress.update(task, description=f"[bold green]✔ Done! Updated metadata for {track_count} tracks!")
