import re
from typing import Iterable, Optional

from curl_cffi import requests as cffi  # browser-TLS client (see note below)

from .base import (
    ArtistImage,
    ArtistImageProvider,
    ProviderResult,
    accept_set,
    normalize_name,
)

# Public autocomplete-search endpoint the Bandcamp search box uses. Returns JSON
# with name + image per result — no API key, no page scraping.
_API = "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic"
_TIMEOUT = 20
# Bandcamp image URLs end in a size suffix (e.g. _23 = search thumb). _10 is the
# full 1200x1200 band photo — same image id, just a larger render.
_SIZE_SUFFIX = re.compile(r"_\d+\.jpg(?:\?.*)?$")


class BandcampProvider(ArtistImageProvider):
    """Bandcamp — strong for underground/electronic artists the other sources miss.

    No API key. Uses the public autocomplete search endpoint (the search box's
    backend), which returns each hit's name + image directly. It must be fetched
    with a **browser-impersonating TLS client** (``curl_cffi``) because Bandcamp's
    edge (Varnish) 403s non-browser TLS fingerprints — plain requests/curl are
    blocked even from a whitelisted IP. Matched by name (verified against the local
    tag / Plex's canonical name); the search thumbnail is upgraded to the full
    1200x1200 band photo."""

    name = "bandcamp"
    requires_mbid = False

    def find(
        self,
        artist_name: str,
        mbid: Optional[str] = None,
        accept_names: Optional[Iterable[str]] = None,
    ) -> ProviderResult:
        if not artist_name:
            return ProviderResult.skipped("no artist name")
        try:
            r = cffi.post(
                _API,
                json={
                    "search_text": artist_name,
                    "search_filter": "b",  # bands & artists (not tracks/albums)
                    "full_page": False,
                    "fan_id": None,
                },
                impersonate="chrome",
                timeout=_TIMEOUT,
            )
            if r.status_code == 429:
                return ProviderResult.rate_limited()
            r.raise_for_status()
            results = (r.json().get("auto") or {}).get("results") or []
        except (
            Exception
        ) as e:  # noqa: BLE001 - curl_cffi/network/json failures → report
            return ProviderResult.error(str(e))
        accept = accept_set(artist_name, accept_names)
        had_name_match = False
        for res in results:
            if res.get("type") != "b":
                continue
            if normalize_name(res.get("name") or "") not in accept:
                continue
            had_name_match = True
            img = res.get("img")
            if img:
                full = _SIZE_SUFFIX.sub("_10.jpg", img)  # thumb → 1200x1200
                return ProviderResult.hit(
                    ArtistImage(
                        url=full,
                        source=self.name,
                        kind="thumb",
                        matched_name=res.get("name"),
                    )
                )
        if had_name_match:
            return ProviderResult.miss("name matched but no image")
        return ProviderResult.miss("no name-matching artist in results")
