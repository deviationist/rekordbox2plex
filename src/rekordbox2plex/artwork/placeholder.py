"""Detect unusable artist images — known placeholders AND solid/near-single-color
images — so they're treated as a non-match.

Two failure modes seen in the wild:
- **Known placeholder** (e.g. Deezer's grey silhouette): a single fixed file served
  under many URLs (empty *and* real-looking md5s). It has a *shape*, so it isn't
  caught by the uniform check — it's identified by content md5. Fingerprints are
  **scoped per provider** (a provider's known placeholder is only tested against
  that provider's own images), since such images are service-specific.
- **Single-color / blank** (e.g. Spotify returns a pure-black image for an artist
  with no photo): no hash needed and provider-agnostic — every channel has a
  near-zero min/max spread. Checked for every source.

Both are cheap on bytes. For URLs we gate on size first: real portraits are large
(50 KB+), whereas placeholders/blank images are small, so we only fetch the body
for small (suspect) images and never download big real ones."""

import hashlib
import io
from typing import Optional, Set

import requests
from PIL import Image

# Known placeholder image fingerprints (md5 of the exact bytes), keyed by the
# provider that serves them. Add new ones (provider → md5) as discovered.
_PLACEHOLDER_MD5 = {
    # Deezer "no photo" grey silhouette (16802 bytes), served under many URLs.
    "deezer": {"3a0adf20e5abdafa2c1f954ca4537f36"},
}
_TIMEOUT = 15
# Only fetch+inspect images at or below this size; larger ⇒ assumed real (a
# blank/placeholder image compresses tiny, a real portrait does not).
_MAX_SUSPECT_BYTES = 30000
# Max per-channel (max-min) spread to still count as "single color".
_UNIFORM_TOL = 12


def _fingerprints(source: Optional[str]) -> Set[str]:
    """Placeholder md5s to test for ``source`` — that provider's set, or (when
    source is None, e.g. a final defensive check) the union of all known ones."""
    if source is None:
        return set().union(*_PLACEHOLDER_MD5.values()) if _PLACEHOLDER_MD5 else set()
    return _PLACEHOLDER_MD5.get(source, set())


def is_placeholder_bytes(content: bytes, source: Optional[str] = None) -> bool:
    """True if the image matches a known placeholder fingerprint for ``source``."""
    return hashlib.md5(content).hexdigest() in _fingerprints(source)


def is_near_uniform_bytes(content: bytes, tol: int = _UNIFORM_TOL) -> bool:
    """True if the image is a single (near-uniform) color — e.g. solid black."""
    try:
        im = Image.open(io.BytesIO(content)).convert("RGB")
    except (OSError, ValueError):
        return False
    # convert("RGB") guarantees a 3-band ((min,max), (min,max), (min,max)) result.
    bands = im.getextrema()
    return all((hi - lo) <= tol for lo, hi in bands)  # type: ignore[misc]


def is_unusable_bytes(content: bytes, source: Optional[str] = None) -> bool:
    """A known placeholder (for ``source``) or a single-color/blank image."""
    return is_placeholder_bytes(content, source) or is_near_uniform_bytes(content)


def is_unusable_url(
    url: str, source: Optional[str] = None, user_agent: str = "rekordbox2plex/0.1"
) -> bool:
    """True if ``url`` is a known placeholder (for ``source``) or a single-color/
    blank image. Gates on Content-Length (HEAD) so large real portraits are never
    downloaded; only small, suspect images are fetched and inspected. Any network
    error → False (don't reject a real image over a transient failure)."""
    headers = {"User-Agent": user_agent}
    try:
        head = requests.head(
            url, headers=headers, timeout=_TIMEOUT, allow_redirects=True
        )
        cl = head.headers.get("Content-Length")
        if cl is not None and cl.isdigit() and int(cl) > _MAX_SUSPECT_BYTES:
            return False  # large ⇒ real image, no body fetched
        r = requests.get(url, headers=headers, timeout=_TIMEOUT)
        r.raise_for_status()
        return is_unusable_bytes(r.content, source)
    except requests.RequestException:
        return False
