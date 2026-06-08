from typing import Iterable, Optional

import requests

from .base import ArtistImage, ArtistImageProvider, ProviderResult

_BASE = "https://webservice.fanart.tv/v3/music"
_TIMEOUT = 15


class FanartTvProvider(ArtistImageProvider):
    """fanart.tv — higher-quality artist art, keyed by MusicBrainz ID. Requires
    a (free) personal API key. Also one of Plex's effective artist-art sources."""

    name = "fanarttv"
    requires_mbid = True

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def find(
        self,
        artist_name: str,
        mbid: Optional[str] = None,
        accept_names: Optional[Iterable[str]] = None,
    ) -> ProviderResult:
        if not self.api_key:
            return ProviderResult.skipped("no FANARTTV_API_KEY")
        if not mbid:
            return ProviderResult.skipped("no MBID for artist")
        try:
            r = requests.get(
                f"{_BASE}/{mbid}", params={"api_key": self.api_key}, timeout=_TIMEOUT
            )
            if r.status_code == 404:
                return ProviderResult.miss("no fanart.tv entry for MBID")
            if r.status_code == 429:
                return ProviderResult.rate_limited()
            r.raise_for_status()
            data = r.json() or {}
        except (requests.RequestException, ValueError) as e:
            return ProviderResult.error(str(e))
        # Posters want a portrait — use artistthumb only; a landscape
        # artistbackground looks wrong in Plex's square poster slot, so we let a
        # later provider supply a real thumb instead of falling back to it.
        thumbs = data.get("artistthumb") or []
        if thumbs:
            return ProviderResult.hit(
                ArtistImage(url=thumbs[0]["url"], source=self.name, kind="thumb")
            )
        return ProviderResult.miss("no artistthumb (portrait) for MBID")
