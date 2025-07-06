from ._RepositoryBase import RepositoryBase, singleton
from ..resolvers.track_resolver import get_track, get_all_tracks
from ..resolvers.library_resolver import get_music_library_name
from ...utils.progress_bar import progress_instance
from ...utils.logger import logger

@singleton
class TrackRepository(RepositoryBase):
    def get_track_id(self, item):
        return item["id"]

    def get_track(self, track_id: str, use_cache: bool = True):
        if use_cache and (cached_track := self._get_from_cache(track_id)):
            return cached_track
        if track := get_track(track_id):
            self._store_single_in_cache(track, self.get_track_id)
            return track
        return False

    def get_all_tracks(self, use_cache: bool = True) -> tuple[tuple, int]:
        if use_cache and self._all_fetched and (cached_tracks := self._get_all_cache()):
            return cached_tracks
        with progress_instance(self._display_progress) as progress:
            library_name = get_music_library_name()
            tracks = get_all_tracks()
            track_count = len(tracks)
            logger.info(f'[cyan]Found {track_count} tracks in Plex library "{library_name}"')
            logger.info("[cyan]Fetching track metadata from Plex...")
            task = progress.add_task("", total=track_count)
            results = []
            for track in tracks:
                progress.update(task, description=f'[cyan]Fetching track metadata for "{track.title}" by "{track.originalTitle}"...')
                try:
                    media = track.media[0]
                    part = media.parts[0]
                    results.append({
                        "id": track.ratingKey,
                        "file_path": part.file,
                        "title": track.title,
                        "added_at": track.addedAt,
                        "track_artist": track.originalTitle,
                        "album_id": track.parentRatingKey,
                        "album_artist_id": track.grandparentRatingKey,
                        "track_object": track,
                    })
                    progress.update(task, description=f'[cyan]Fetched track metadata for "{track.title}" by "{track.originalTitle}"...')
                except (IndexError, AttributeError):
                    logger.info(f'[red]No file path found for "{track.title}"')
                finally:
                    progress.update(task, advance=1)
                progress.update(task, description=f"[bold green]✔ Done! Fetched metadata for {track_count} tracks!")
            self._store_in_cache(results, self.get_track_id)
            return results, len(results)
