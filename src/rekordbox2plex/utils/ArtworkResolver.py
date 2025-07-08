from PIL import Image
from typing import List, Dict, Optional, Tuple
from ..rekordbox.data_types import TrackWithArtwork
from ..config import get_rekordbox_folder_path
from ..utils.logger import logger
import imagehash
import os


class ArtworkResolver:
    def __init__(self, tracks: List[TrackWithArtwork]):
        self.tracks = tracks
        self.set_rb_folder_path()
        self._hash_cache: Dict[str, imagehash.ImageHash] = (
            {}
        )  # Cache for computed hashes

    def set_rb_folder_path(self):
        rb_folder_path = get_rekordbox_folder_path()
        if not rb_folder_path:
            raise Exception(
                'Cannot resolve artwork due to environment variable "REKORDBOX_FOLDER_PATH" not being set.'
            )
        self.rb_folder_path = rb_folder_path

    def replace_rekordbox_root(self, full_path: str) -> str:
        """Replace rekordbox root path with actual folder path."""
        marker = "/rekordbox/"
        if marker not in full_path:
            raise ValueError(f"Path does not contain '{marker}': {full_path}")

        # Split the path at '/rekordbox/' and keep the part after it
        after_marker = full_path.split(marker, 1)[1]

        # Join with the new rb_folder_path
        new_path = os.path.join(self.rb_folder_path.rstrip("/"), after_marker)
        return new_path

    def resolve_unique_artwork_paths(self) -> List[Tuple[TrackWithArtwork, str]]:
        """Get unique artwork paths from tracks."""
        unique_artwork_paths = []
        seen_paths = set()

        for track in self.tracks:
            if track.artwork_local_path is not None:
                try:
                    real_artwork_path = self.replace_rekordbox_root(
                        track.artwork_local_path
                    )

                    # Check if path exists and is readable
                    if (
                        os.path.exists(real_artwork_path)
                        and real_artwork_path not in seen_paths
                    ):
                        seen_paths.add(real_artwork_path)
                        unique_artwork_paths.append((track, real_artwork_path))

                except (ValueError, OSError) as e:
                    logger.warning(f"Skipping invalid artwork path for track: {e}")
                    continue

        return unique_artwork_paths

    def get_image_hash(self, image_path: str) -> Optional[imagehash.ImageHash]:
        """Get image hash with caching and error handling."""
        if image_path in self._hash_cache:
            return self._hash_cache[image_path]

        try:
            with Image.open(image_path) as img:
                hash_value = imagehash.average_hash(img)
                self._hash_cache[image_path] = hash_value
                return hash_value
        except Exception as e:
            logger.error(f"Failed to compute hash for {image_path}: {e}")
            return None

    def are_images_similar(
        self, img1_path: str, img2_path: str, threshold: int = 5
    ) -> bool:
        """Check if two images are similar using perceptual hashing."""
        hash1 = self.get_image_hash(img1_path)
        hash2 = self.get_image_hash(img2_path)

        if hash1 is None or hash2 is None:
            return False

        similarity = abs(hash1 - hash2) <= threshold
        logger.debug(
            f"Image similarity: {similarity} (distance: {abs(hash1 - hash2)}) for {img1_path} vs {img2_path}"
        )
        return similarity

    def resolve_unique_artworks(
        self, unique_artwork_paths: List[Tuple[TrackWithArtwork, str]]
    ) -> List[Tuple[TrackWithArtwork, str]]:
        """Resolve truly unique artworks by comparing image similarity."""
        if not unique_artwork_paths:
            return []

        unique_artworks: List[Tuple[TrackWithArtwork, str]] = []

        for track, current_path in unique_artwork_paths:
            is_duplicate = False

            # Compare against all existing unique artworks
            for existing_track, existing_path in unique_artworks:
                if self.are_images_similar(current_path, existing_path):
                    logger.debug(
                        f"Found duplicate artwork: {current_path} similar to {existing_path}"
                    )
                    is_duplicate = True
                    break

            # If not a duplicate, add to unique artworks
            if not is_duplicate:
                unique_artworks.append((track, current_path))
                logger.debug(f"Added unique artwork: {current_path}")

        return unique_artworks

    def resolve(self) -> Optional[Tuple[TrackWithArtwork, str]]:
        """
        Resolve artwork for an album.

        Returns:
            Tuple of (track, artwork_path) if exactly one unique artwork found,
            None otherwise.
        """
        unique_artwork_paths = self.resolve_unique_artwork_paths()

        if not unique_artwork_paths:
            logger.debug("No artwork paths found")
            return None

        logger.debug(
            f"Found {len(unique_artwork_paths)} unique artwork paths, checking for duplicates"
        )

        unique_artworks = self.resolve_unique_artworks(unique_artwork_paths)
        unique_artworks_count = len(unique_artworks)

        if unique_artworks_count == 1:
            logger.debug("Found exactly 1 unique artwork")
            return unique_artworks[0]
        elif unique_artworks_count == 0:
            logger.debug("No valid unique artworks found")
            return None
        else:
            logger.debug(
                f"Found {unique_artworks_count} different artworks, cannot determine single album artwork"
            )
            # Optionally, you could return the first one or implement additional logic
            return None

    def get_all_unique_artworks(self) -> List[Tuple[TrackWithArtwork, str]]:
        """Get all unique artworks (useful for debugging or when multiple artworks are expected)."""
        unique_artwork_paths = self.resolve_unique_artwork_paths()
        return self.resolve_unique_artworks(unique_artwork_paths)

    def clear_cache(self):
        """Clear the hash cache to free memory."""
        self._hash_cache.clear()
