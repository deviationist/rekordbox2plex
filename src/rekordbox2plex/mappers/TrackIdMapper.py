from ..plex.repositories.TrackRepository import TrackRepository as PlexTrackRepository
from ..plex.data_types import PlexTrackWrapper
from ..rekordbox.resolvers.track import resolve_track_id
from ..utils.progress_bar import progress_instance
from ..utils.helpers import build_track_string, progress_count
from ..utils.logger import logger
from typing import Dict, Literal


class TrackIdMapper:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TrackIdMapper, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.rekordbox_index: Dict[int, PlexTrackWrapper] = {}
        self._initialized = True
        self._all_mapped = False

    def map(self, plex_track: PlexTrackWrapper, rb_track_id: int) -> None:
        self.rekordbox_index[int(rb_track_id)] = plex_track

    def resolve_plex_track_by_rb(
        self, rekordbox_id: int
    ) -> PlexTrackWrapper | Literal[False]:
        self.ensure_mappings()
        plex_track = self.rekordbox_index.get(int(rekordbox_id))
        if plex_track:
            return plex_track
        return False

    def ensure_mappings(self) -> None:
        if self._all_mapped:
            return
        logger.info("[cyan]No tracks mapped yet, let's fetch all the tracks...")
        try:
            plex_tracks, track_count = PlexTrackRepository().get_all_tracks()
            with progress_instance() as progress:
                task = progress.add_task("", total=track_count)
                successful_mappings = 0
                count_string = progress_count(0, track_count)

                for i, plex_track in enumerate(plex_tracks):
                    count_string = progress_count(i, track_count)
                    track_string = build_track_string(plex_track)
                    progress.update(
                        task,
                        description=f"[cyan]({count_string}) Resolving {track_string}...",
                    )

                    try:
                        rb_id = resolve_track_id(plex_track, progress, task)
                        if rb_id is not None:
                            self.map(plex_track, rb_id)
                            successful_mappings += 1
                    except Exception as e:
                        logger.warning(f"Failed to resolve track {track_string}: {e}")

                    progress.update(task, advance=1)

                progress.update(
                    task,
                    description=f"[bold green]({count_string}) ✔ Done! Mapped {successful_mappings}/{track_count} tracks!",
                )
            self._all_mapped = True
        except Exception as e:
            logger.error(f"Failed to build track mappings: {e}")
            raise
