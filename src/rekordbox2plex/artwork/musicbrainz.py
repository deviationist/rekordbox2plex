"""Resolve an artist name → MusicBrainz Artist ID (MBID).

Needed by MBID-keyed providers (fanart.tv). MusicBrainz asks clients to send a
descriptive User-Agent and to stay at ~1 request/second; we honour both. Results
are cached per process and failures resolve to None."""

import threading
import time
from typing import Dict, Optional, Tuple

import requests

_URL = "https://musicbrainz.org/ws/2/artist"
_TIMEOUT = 15
_MIN_INTERVAL = 1.1  # seconds between requests (MusicBrainz rate limit)
_MIN_SCORE = 90  # default: only accept confident matches


class MusicBrainzResolver:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        # keyed by (name, min_score) so the same name can be resolved at different
        # confidence thresholds (e.g. stricter for split-collab pieces)
        self._cache: Dict[Tuple[str, int], Optional[str]] = {}
        self._last_request = 0.0
        # MusicBrainz requires ~1 req/s, so calls must be serialized even when
        # the action runs artists concurrently.
        self._lock = threading.Lock()

    def _throttle(self) -> None:
        wait = _MIN_INTERVAL - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def mbid_for(
        self, artist_name: str, min_score: Optional[int] = None
    ) -> Optional[str]:
        if not artist_name:
            return None
        threshold = _MIN_SCORE if min_score is None else min_score
        key = (artist_name, threshold)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            mbid: Optional[str] = None
            try:
                self._throttle()
                r = requests.get(
                    _URL,
                    params={
                        "query": f'artist:"{artist_name}"',
                        "fmt": "json",
                        "limit": "1",
                    },
                    headers={"User-Agent": self.user_agent},
                    timeout=_TIMEOUT,
                )
                r.raise_for_status()
                artists = (r.json() or {}).get("artists") or []
                if artists and int(artists[0].get("score", 0)) >= threshold:
                    mbid = artists[0].get("id")
            except (requests.RequestException, ValueError):
                mbid = None
            self._cache[key] = mbid
            return mbid
