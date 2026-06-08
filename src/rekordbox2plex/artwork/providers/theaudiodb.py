from typing import Iterable, Optional, Tuple

import requests

from .base import (
    ArtistImage,
    ArtistImageProvider,
    ProviderResult,
    accept_set,
    normalize_name,
)

_BASE = "https://www.theaudiodb.com/api/v1/json"
_TIMEOUT = 15


class TheAudioDBProvider(ArtistImageProvider):
    """TheAudioDB — free artist-image API, matched by MusicBrainz ID when
    available (most reliable) or else by artist name. One of the sources Plex's
    own music metadata draws on. The free/test key ("2") is heavily rate-limited
    under concurrency — set THEAUDIODB_API_KEY for headroom."""

    name = "theaudiodb"
    requires_mbid = False  # can use MBID if given, but works by name too

    def __init__(self, api_key: str = "2") -> None:
        # "2" is TheAudioDB's free/test key; users can set their own.
        self.api_key = api_key

    def _query(self, params_path: str, params: dict) -> Tuple[Optional[dict], str]:
        """Return (artist_dict_or_None, status). status ∈ ok/rate_limited/error."""
        try:
            r = requests.get(
                f"{_BASE}/{self.api_key}/{params_path}", params=params, timeout=_TIMEOUT
            )
            if r.status_code == 429:
                return None, "rate_limited"
            r.raise_for_status()
            artists = (r.json() or {}).get("artists") or []
            return (artists[0] if artists else None), "ok"
        except (requests.RequestException, ValueError) as e:
            return None, f"error:{e}"

    def find(
        self,
        artist_name: str,
        mbid: Optional[str] = None,
        accept_names: Optional[Iterable[str]] = None,
    ) -> ProviderResult:
        artist = None
        if mbid:
            # MBID lookup is authoritative — no name verification needed.
            artist, status = self._query("artist-mb.php", {"i": mbid})
            if status == "rate_limited":
                return ProviderResult.rate_limited()
            if status.startswith("error"):
                return ProviderResult.error(status[6:])
        if artist is None and artist_name:
            found, status = self._query("search.php", {"s": artist_name})
            if status == "rate_limited":
                return ProviderResult.rate_limited()
            if status.startswith("error"):
                return ProviderResult.error(status[6:])
            # Name search is fuzzy — verify the returned name matches.
            if found is not None:
                accept = accept_set(artist_name, accept_names)
                if normalize_name(found.get("strArtist") or "") in accept:
                    artist = found
                else:
                    return ProviderResult.miss("name did not match search result")
        if artist is None:
            return ProviderResult.miss("no artist matched")
        # Posters want a portrait — use strArtistThumb only (not the landscape
        # strArtistFanart), letting a later provider supply a real thumb instead.
        name = artist.get("strArtist")
        thumb = artist.get("strArtistThumb")
        if thumb:
            return ProviderResult.hit(
                ArtistImage(
                    url=thumb, source=self.name, kind="thumb", matched_name=name
                )
            )
        return ProviderResult.miss("artist has no thumb (portrait)")
