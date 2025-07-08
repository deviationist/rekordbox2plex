from ..plex.repositories.TrackRepository import TrackRepository
from ..plex.data_types import PlexTrackWrapper
from ..rekordbox.resolvers.track import resolve_track
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
        self.mappings = {}  # plexId -> full mapping data
        self.rekordbox_lookup = {}  # rekordboxId -> plexId for reverse lookup
        self._initialized = True

    def map(self, plex_track: PlexTrackWrapper, rb_item: ResolvedTrack):
        """
        Map a complete Plex track to Rekordbox item data

        Args:
            plex_track: Dictionary containing Plex track data with 'id' key
            rb_item: Tuple of (track, artist, artwork, album, albumArtist) from Rekordbox
        """
        plex_id = plex_track.id
        rekordbox_id = rb_item.track.id

        # Store the complete mapping
        mapping_data = {"plex_track": plex_track, "rekordbox": rb_item}

        self.mappings[plex_id] = mapping_data
        self.rekordbox_lookup[rekordbox_id] = plex_id

    def resolve_rb_track_by_plex(self, plex_id: int) -> ResolvedTrack | Literal[False]:
        """
        Get the Rekordbox data for a given Plex ID

        Args:
            plex_id: Plex track ID

        Returns:
            Dictionary with rekordbox data or empty string if not found
        """

        self.ensure_mappings()

        mapping = self.mappings.get(plex_id)
        if mapping:
            return mapping["rekordbox"]
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

        plex_id = self.rekordbox_lookup.get(rekordbox_id)
        if plex_id and plex_id in self.mappings:
            return self.mappings[plex_id]["plex_track"]
        return False

    def ensure_mappings(self):
        if len(self.mappings) == 0:
            logger.info(
                "[cyan]No track mappings (Rekordbox <-> Plex) found, fetching tracks..."
            )
            plex_tracks, track_count = TrackRepository().get_all_tracks()
            with progress_instance() as progress:
                task = progress.add_task("", total=track_count)
                for plex_track in plex_tracks:
                    track_string = build_track_string(plex_track)
                    progress.update(
                        task,
                        description=f"[yellow]Resolving track metadata {track_string}...",
                    )
                    rb_item = resolve_track(plex_track, progress, task)
                    progress.update(
                        task,
                        advance=1,
                        description=f"[yellow]Resolved track metadata {track_string}...",
                    )
                    self.map(plex_track, rb_item)
                progress.update(
                    task,
                    description=f"[bold green]✔ Done! Resolved track metadata for {track_count} tracks!",
                )
