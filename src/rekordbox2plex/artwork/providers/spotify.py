import threading
import time
from typing import Iterable, Optional

import requests

from .base import (
    ArtistImage,
    ArtistImageProvider,
    ProviderResult,
    accept_set,
    normalize_name,
)

_TOKEN_URL = "https://accounts.spotify.com/api/token"
_SEARCH = "https://api.spotify.com/v1/search"
_TIMEOUT = 15


class SpotifyProvider(ArtistImageProvider):
    """Spotify — excellent coverage/quality for modern & electronic artists.
    Authenticates with the **client-credentials** flow (a free app's client id +
    secret, no user login); the app token is cached and refreshed automatically.
    Matched by name (Spotify search) with name-verification; uses the largest
    artist image."""

    name = "spotify"
    requires_mbid = False

    def __init__(self, client_id: Optional[str], client_secret: Optional[str]) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expires = 0.0

    def _get_token(self) -> Optional[str]:
        if not (self.client_id and self.client_secret):
            return None
        with self._lock:
            if self._token and time.monotonic() < self._expires:
                return self._token
            r = requests.post(
                _TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            j = r.json() or {}
            self._token = j.get("access_token")
            self._expires = time.monotonic() + int(j.get("expires_in", 3600)) - 60
            return self._token

    def find(
        self,
        artist_name: str,
        mbid: Optional[str] = None,
        accept_names: Optional[Iterable[str]] = None,
    ) -> ProviderResult:
        if not (self.client_id and self.client_secret):
            return ProviderResult.skipped("no SPOTIFY_CLIENT_ID/SECRET")
        if not artist_name:
            return ProviderResult.skipped("no artist name")
        try:
            token = self._get_token()
            r = requests.get(
                _SEARCH,
                params={"q": artist_name, "type": "artist", "limit": "10"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=_TIMEOUT,
            )
            if r.status_code == 429:
                return ProviderResult.rate_limited()
            r.raise_for_status()
            items = ((r.json() or {}).get("artists") or {}).get("items") or []
        except requests.RequestException as e:
            return ProviderResult.error(str(e))
        except ValueError as e:
            return ProviderResult.error(f"bad json: {e}")
        accept = accept_set(artist_name, accept_names)
        had_name_match = False
        for it in items:
            if normalize_name(it.get("name") or "") not in accept:
                continue
            had_name_match = True
            images = it.get("images") or []
            if not images:  # Spotify returns images largest-first
                continue
            # Usability (Spotify serves a black image for no-photo artists) is
            # validated centrally by the action, uniformly across all providers.
            return ProviderResult.hit(
                ArtistImage(
                    url=images[0]["url"],
                    source=self.name,
                    kind="thumb",
                    matched_name=it.get("name"),
                )
            )
        if had_name_match:
            return ProviderResult.miss("name matched but no image")
        return ProviderResult.miss("no name-matching artist in results")
