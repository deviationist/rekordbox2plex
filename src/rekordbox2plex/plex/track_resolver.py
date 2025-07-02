from rich.console import Console
from ..progress_bar import progress_instance
from .library_resolver import get_music_library

console = Console()

def fetch_track(id):
    music_library, library_name = get_music_library()
    return music_library.fetchItem(id)

def fetch_tracks() -> tuple[tuple, int]:
    with progress_instance() as progress:
        music_library, library_name = get_music_library()

        # Get all tracks
        #tracks = music_library.searchTracks(maxresults=500)
        tracks = music_library.searchTracks()

        track_count = len(tracks)
        console.log(f"[cyan]Found {track_count} tracks in Plex library {library_name}")
        console.log("[cyan]Fetching track metadata...")
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
                    #"album_artist": track.artist(),
                    #"album": track.album(),
                    "track_object": track,
                })
                progress.update(task, description=f'[cyan]Fetched track metadata for "{track.title}" by "{track.originalTitle}"...')
            except (IndexError, AttributeError):
                console.log(f"[red]{track.title} -> No file path found")
            finally:
                progress.update(task, advance=1)
            progress.update(task, description=f"[bold green]✔ Done! Fetched metadata for {track_count} tracks!")
        return results, track_count
