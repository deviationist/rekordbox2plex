import re
from typing import Iterable, Optional

import requests

from .base import (
    ArtistImage,
    ArtistImageProvider,
    ProviderResult,
    accept_set,
    normalize_name,
)

_SEARCH = "https://api.deezer.com/search/artist"
_TIMEOUT = 15
# Deezer's "no photo" grey silhouette is served at an EMPTY-id URL — the picture
# fields come back as ".../images/artist//<size>-...jpg" (note the double slash).
# That's the deterministic no-image signal, independent of the file's size/md5.
_EMPTY_PICTURE = re.compile(r"/images/[a-z]+//")


class DeezerProvider(ArtistImageProvider):
    """Deezer — free public API, **no auth required**, broad coverage of modern /
    electronic artists with good square portraits (``picture_xl``). Matched by
    name (Deezer search) with name-verification against the local tag / Plex's
    canonical name to avoid same-name mismatches."""

    name = "deezer"
    requires_mbid = False

    def __init__(self, user_agent: str = "rekordbox2plex/0.1") -> None:
        self.user_agent = user_agent

    def find(
        self,
        artist_name: str,
        mbid: Optional[str] = None,
        accept_names: Optional[Iterable[str]] = None,
    ) -> ProviderResult:
        if not artist_name:
            return ProviderResult.skipped("no artist name")
        try:
            r = requests.get(
                _SEARCH,
                params={"q": artist_name, "limit": "10"},
                headers={"User-Agent": self.user_agent},
                timeout=_TIMEOUT,
            )
            if r.status_code == 429:
                return ProviderResult.rate_limited()
            r.raise_for_status()
            data = (r.json() or {}).get("data") or []
        except requests.RequestException as e:
            return ProviderResult.error(str(e))
        except ValueError as e:
            return ProviderResult.error(f"bad json: {e}")
        accept = accept_set(artist_name, accept_names)
        had_name_match = False
        for res in data:
            if normalize_name(res.get("name") or "") not in accept:
                continue
            had_name_match = True
            url = res.get("picture_xl") or res.get("picture_big") or res.get("picture")
            if url and not _EMPTY_PICTURE.search(url):
                # Usability (placeholder / blank / single-color) is also validated
                # centrally by the action, uniformly across all providers.
                return ProviderResult.hit(
                    ArtistImage(
                        url=url,
                        source=self.name,
                        kind="thumb",
                        matched_name=res.get("name"),
                    )
                )
        if had_name_match:
            return ProviderResult.miss("name matched but no picture")
        return ProviderResult.miss("no name-matching artist in results")
