from PIL import Image
import io
import imagehash


class ImageHashComparer:
    def load_images(
        self, image1: bytes | str, image2: bytes | str
    ) -> "ImageHashComparer":
        self._image1 = (
            Image.open(image1)
            if isinstance(image1, str)
            else Image.open(io.BytesIO(image1))
        )
        self._image2 = (
            Image.open(image2)
            if isinstance(image2, str)
            else Image.open(io.BytesIO(image2))
        )
        return self

    def compare(self, threshold: int = 5) -> tuple[bool, int]:
        hash1 = imagehash.average_hash(self._image1)
        hash2 = imagehash.average_hash(self._image2)
        if hash1 is None or hash2 is None:
            return False
        distance = hash1 - hash2
        similarity = distance <= threshold
        return similarity, distance

    def exec(
        self, image1: bytes | str, image2: bytes | str, threshold: int = 5
    ) -> tuple[bool, int]:
        """
        Compare two images using average hash and return True if they are similar
        within the given threshold.
        """
        self.load_images(image1, image2)
        return self.compare(threshold)
