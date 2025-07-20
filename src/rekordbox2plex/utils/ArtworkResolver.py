from ..config import get_rekordbox_folder_path
import os


class ArtworkResolver:
    def __init__(self) -> None:
        self.rb_folder_path = self.get_rb_folder_path()

    def get_rb_folder_path(self) -> str:
        rb_folder_path = get_rekordbox_folder_path()
        if not rb_folder_path:
            raise Exception(
                'Cannot resolve artwork due to environment variable "REKORDBOX_FOLDER_PATH" not being set.'
            )
        return rb_folder_path

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
