from ..plex.repositories.TrackRepository import TrackRepository
from ..plex.data_types import PlexTrackWrapper
from ..rekordbox.resolvers.track import resolve_track as resolve_track_in_rekordbox
from ..rekordbox.data_types import ResolvedTrack
from ..utils.progress_bar import progress_instance
from ..utils.helpers import build_track_string
from ..utils.logger import logger
from typing import Literal


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
        self.plex_index = {}
        self.rekordbox_index = {}
        self._initialized = True
        self._all_mapped = False

    def map(self, plex_track: PlexTrackWrapper, rb_item: ResolvedTrack):
        """
        Map a complete Plex track to Rekordbox item data

        Args:
            plex_track: Dictionary containing Plex track data with 'id' key
            rb_item: Tuple of (track, artist, artwork, album, albumArtist) from Rekordbox
        """
        plex_id = int(plex_track.id)
        rekordbox_id = int(rb_item.track.id)

        self.plex_index[plex_id] = rb_item
        self.rekordbox_index[rekordbox_id] = plex_track

    def resolve_rb_track_by_plex(self, plex_id: int) -> ResolvedTrack | Literal[False]:
        """
        Get the Rekordbox data for a given Plex ID

        Args:
            plex_id: Plex track ID

        Returns:
            Dictionary with rekordbox data or empty string if not found
        """

        self.ensure_mappings()

        rb_item = self.plex_index.get(int(plex_id))
        if rb_item:
            return rb_item
        return False

    def resolve_plex_track_by_rb(
        self, rekordbox_id: int
    ) -> PlexTrackWrapper | Literal[False]:
        """
        Get the Plex track data for a given Rekordbox ID

        Args:
            rekordbox_id: Rekordbox track ID

        Returns:
            Dictionary with plex track data or empty string if not found
        """

        self.ensure_mappings()

        plex_track = self.rekordbox_index.get(int(rekordbox_id))
        if plex_track:
            return plex_track
        return False

    def all_tracks_mapped(self):
        self._all_mapped = True

    def ensure_mappings(self):
        if not self._all_mapped:
            logger.info("[cyan]No track mappings found, fetching tracks...")
            try:
                plex_tracks, track_count = TrackRepository().get_all_tracks()
                with progress_instance() as progress:
                    task = progress.add_task("", total=track_count)
                    successful_mappings = 0

                    for plex_track in plex_tracks:
                        track_string = build_track_string(plex_track)
                        progress.update(
                            task, description=f"[yellow]Resolving {track_string}..."
                        )

                        try:
                            rb_item = resolve_track_in_rekordbox(
                                plex_track, progress, task
                            )
                            if rb_item:  # Only map if resolution succeeded
                                self.map(plex_track, rb_item)
                                successful_mappings += 1
                        except Exception as e:
                            logger.warning(
                                f"Failed to resolve track {track_string}: {e}"
                            )

                        progress.update(task, advance=1)

                    progress.update(
                        task,
                        description=f"[bold green]✔ Done! Mapped {successful_mappings}/{track_count} tracks!",
                    )
                self._all_mapped = True
            except Exception as e:
                logger.error(f"Failed to build track mappings: {e}")
                raise
