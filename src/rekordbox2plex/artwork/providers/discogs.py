import threading
import time
from typing import Dict, Iterable, Optional

import requests

from .base import (
    ArtistImage,
    ArtistImageProvider,
    ProviderResult,
    accept_set,
    normalize_name,
)

_SEARCH = "https://api.discogs.com/database/search"
_TIMEOUT = 15
_MIN_INTERVAL = 1.05  # authenticated Discogs limit is 60/min → ~1 req/s


class DiscogsProvider(ArtistImageProvider):
    """Discogs — the strongest source for electronic/underground artists (and one
    of the sources Plex itself uses). Matches by artist name (Discogs has no MBID
    key); the search result carries the artist's image directly. Authenticates
    with either a personal token OR a consumer key+secret. Throttled to the
    60/min authenticated rate limit so it's safe under concurrency."""

    name = "discogs"
    requires_mbid = False

    def __init__(
        self,
        user_agent: str,
        token: Optional[str] = None,
        key: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> None:
        self.user_agent = user_agent
        self.token = token
        self.key = key
        self.secret = secret
        self._lock = threading.Lock()
        self._last = 0.0

    def _auth(self) -> Optional[Dict[str, str]]:
        if self.token:
            return {"token": self.token}
        if self.key and self.secret:
            return {"key": self.key, "secret": self.secret}
        return None

    def _throttle(self) -> None:
        wait = _MIN_INTERVAL - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def find(
        self,
        artist_name: str,
        mbid: Optional[str] = None,
        accept_names: Optional[Iterable[str]] = None,
    ) -> ProviderResult:
        auth = self._auth()
        if auth is None:
            return ProviderResult.skipped("no DISCOGS_TOKEN or DISCOGS_KEY/SECRET")
        if not artist_name:
            return ProviderResult.skipped("no artist name")
        try:
            with self._lock:
                self._throttle()
                r = requests.get(
                    _SEARCH,
                    params={
                        "type": "artist",
                        "q": artist_name,
                        "per_page": "10",
                        **auth,
                    },
                    headers={"User-Agent": self.user_agent},
                    timeout=_TIMEOUT,
                )
            if r.status_code == 429:
                return ProviderResult.rate_limited()
            r.raise_for_status()
            results = (r.json() or {}).get("results") or []
        except requests.RequestException as e:
            return ProviderResult.error(str(e))
        except ValueError as e:
            return ProviderResult.error(f"bad json: {e}")
        # Discogs search is fuzzy — only accept a result whose name actually matches
        # the artist (local tag or Plex's canonical name), not just the top hit.
        accept = accept_set(artist_name, accept_names)
        had_name_match = False
        for res in results:
            title = res.get("title") or ""
            if normalize_name(title) not in accept:
                continue
            had_name_match = True
            url = res.get("cover_image") or res.get("thumb")
            # Discogs serves a generic spacer for artists with no image — skip it.
            if url and "spacer.gif" not in url:
                return ProviderResult.hit(
                    ArtistImage(
                        url=url, source=self.name, kind="thumb", matched_name=title
                    )
                )
        if had_name_match:
            return ProviderResult.miss("name matched but no image")
        return ProviderResult.miss("no name-matching artist in results")
