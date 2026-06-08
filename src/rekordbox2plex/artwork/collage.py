"""Compose multiple artist portraits into a single poster (for collab entities).

Downloads each member image and arranges them as side-by-side vertical panels
(cover-cropped) into one square JPEG — a meaningful poster for a Plex "artist"
that is really a comma-joined collaboration. Members that fail to download are
skipped; returns False if none could be fetched."""

import io
import time
from typing import List, Optional, Tuple

import requests
from PIL import Image

from .placeholder import is_unusable_bytes

_TIMEOUT = 20
_ATTEMPTS = 3
# Some image CDNs (Discogs especially) block bare python-requests / throttle
# bursts — send a real UA and retry transient failures.
_HEADERS = {"User-Agent": "rekordbox2plex/0.1 ( artist-collage )"}


def _cover_crop(im: Image.Image, w: int, h: int) -> Image.Image:
    """Scale to cover a w×h box, then center-crop (no distortion/letterboxing)."""
    sw, sh = im.size
    scale = max(w / sw, h / sh)
    resized = im.resize((max(1, round(sw * scale)), max(1, round(sh * scale))))
    rw, rh = resized.size
    left, top = (rw - w) // 2, (rh - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _fetch(url: str) -> Optional[Image.Image]:
    """Return the image, or None if it can't be fetched / is a known placeholder
    (which should never become a collage panel)."""
    for i in range(_ATTEMPTS):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            if is_unusable_bytes(r.content):
                return None  # placeholder or blank/single-color — skip, don't retry
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        except (requests.RequestException, OSError, ValueError):
            time.sleep(0.4 * (i + 1))  # brief backoff on throttle/transient
    return None


def compose_strips(
    urls: List[str],
    out_path: str,
    size: int = 600,
    divider: int = 6,
    bg: Tuple[int, int, int] = (18, 18, 18),
) -> bool:
    """Compose ``urls`` into a square poster of N vertical panels at ``out_path``.
    Returns True on success, False if no image could be fetched."""
    imgs: List[Image.Image] = []
    for u in urls:
        im = _fetch(u)
        if im is not None:
            imgs.append(im)
    if not imgs:
        return False
    n = len(imgs)
    canvas = Image.new("RGB", (size, size), bg)
    panel_w = (size - divider * (n - 1)) // n
    x = 0
    for i, im in enumerate(imgs):
        # last panel takes the rounding remainder so it reaches the right edge
        w = panel_w if i < n - 1 else size - x
        canvas.paste(_cover_crop(im, w, size), (x, 0))
        x += w + divider
    canvas.save(out_path, "JPEG", quality=90)
    return True
