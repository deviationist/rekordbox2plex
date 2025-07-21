from ._RepositoryBase import RepositoryBase, singleton
from ..resolvers.track import get_track, get_all_tracks
from ..resolvers.library import get_music_library_name
from ...utils.progress_bar import progress_instance
from ...utils.logger import logger
from ...utils.helpers import progress_count
from typing import List, Tuple
from ..data_types import PlexTrack, PlexTrackWrapper, CacheItems


@singleton
class TrackRepository(RepositoryBase):
    def get_track_id(self, item) -> int:
        return item.id

    def get_track(self, track_id: int, use_cache: bool = True) -> PlexTrack:
        if use_cache and (cached_track := self._get_from_cache(str(track_id))):
            return cached_track
        if track := get_track(track_id):
            if use_cache:
                self._store_single_in_cache(track, self.get_track_id)
            return track
        return None

    def get_all_tracks(
        self, use_cache: bool = True
    ) -> Tuple[List[PlexTrackWrapper] | CacheItems, int]:
        if use_cache and self._all_fetched and (cached_tracks := self._get_all_cache()):
            return cached_tracks, len(cached_tracks)
        with progress_instance(self._display_progress) as progress:
            library_name = get_music_library_name()
            tracks = get_all_tracks()
            track_count = len(tracks)
            logger.info(
                f'[cyan]Found {track_count} tracks in Plex library "{library_name}"'
            )
            logger.info("[cyan]Fetching track metadata from Plex...")
            task = progress.add_task("", total=track_count)
            results = []
            for i, track in enumerate(tracks):
                count_string = progress_count(i, track_count)
                progress.update(
                    task,
                    description=f'[cyan]({count_string}) Fetching track metadata for "{track.title}" by "{track.originalTitle}"...',
                )
                try:
                    media = track.media[0]
                    part = media.parts[0]
                    results.append(
                        PlexTrackWrapper(
                            id=track.ratingKey,
                            track_title=track.title,
                            track_artist_name=track.originalTitle,
                            album_id=track.parentRatingKey,
                            album_name=track.parentTitle,
                            album_artist_id=track.grandparentRatingKey,
                            album_artist_name=track.grandparentTitle,
                            track_object=track,
                            file_path=part.file,
                            added_at=track.addedAt,
                            has_artwork=bool(track.thumb),
                        )
                    )
                    progress.update(
                        task,
                        description=f'[cyan]({count_string}) Fetched track metadata for "{track.title}" by "{track.originalTitle}"...',
                    )
                except (IndexError, AttributeError):
                    logger.info(f'[red]No file path found for "{track.title}"')
                finally:
                    progress.update(task, advance=1)
            progress.update(
                task,
                description=f"[bold green]({count_string}) ✔ Done! Fetched metadata for {track_count} tracks!",
            )
            if use_cache:
                self._store_in_cache(results, self.get_track_id)
            return results, len(results)
