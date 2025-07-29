from ..utils.logger import logger
from ._ActionBase import ActionBase


class TrackWipe(ActionBase):
    def __init__(self) -> None:
        super().__init__("Track wipe")
        self.delete_count = 0

    def wipe(self):
        logger.info(
            "[cyan]Attempting to wipe all tracks in Plex..."
        )
        pass
