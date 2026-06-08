"""Build the ordered list of artist-image providers from config."""

from typing import List

from ..config import (
    get_discogs_key,
    get_discogs_secret,
    get_discogs_token,
    get_fanarttv_api_key,
    get_musicbrainz_user_agent,
    get_spotify_client_id,
    get_spotify_client_secret,
    get_theaudiodb_api_key,
)
from ..utils.logger import logger
from .providers import (
    ArtistImageProvider,
    BandcampProvider,
    DeezerProvider,
    DiscogsProvider,
    FanartTvProvider,
    SpotifyProvider,
    TheAudioDBProvider,
)

# Known driver names. Add new sources here + a branch in build_providers().
_KNOWN = ("fanarttv", "theaudiodb", "deezer", "spotify", "bandcamp", "discogs")


def build_providers(names: List[str]) -> List[ArtistImageProvider]:
    """Instantiate art providers for the given names, in priority order. Unknown
    names warn and are skipped; discogs/fanarttv are skipped (with a warning) when
    their credentials are unset. (MBID resolution — including Plex's own match —
    is handled by the action, not a provider.)"""
    providers: List[ArtistImageProvider] = []
    for name in names:
        n = name.strip().lower()
        if n == "discogs":
            token, key, secret = (
                get_discogs_token(),
                get_discogs_key(),
                get_discogs_secret(),
            )
            if not token and not (key and secret):
                logger.warning(
                    "[yellow]Provider 'discogs' requested but no DISCOGS_TOKEN (or "
                    "DISCOGS_KEY + DISCOGS_SECRET) is set — skipping it."
                )
                continue
            providers.append(
                DiscogsProvider(
                    get_musicbrainz_user_agent(), token=token, key=key, secret=secret
                )
            )
        elif n == "theaudiodb":
            providers.append(TheAudioDBProvider(get_theaudiodb_api_key()))
        elif n == "deezer":
            providers.append(DeezerProvider(get_musicbrainz_user_agent()))
        elif n == "bandcamp":
            providers.append(BandcampProvider())
        elif n == "spotify":
            cid, secret = get_spotify_client_id(), get_spotify_client_secret()
            if not (cid and secret):
                logger.warning(
                    "[yellow]Provider 'spotify' requested but SPOTIFY_CLIENT_ID/"
                    "SECRET are unset — skipping it."
                )
                continue
            providers.append(SpotifyProvider(cid, secret))
        elif n == "fanarttv":
            fkey = get_fanarttv_api_key()
            if not fkey:
                logger.warning(
                    "[yellow]Provider 'fanarttv' requested but FANARTTV_API_KEY is "
                    "unset — skipping it."
                )
                continue
            providers.append(FanartTvProvider(fkey))
        else:
            logger.warning(
                f"[yellow]Unknown artist-image provider {name!r} "
                f"(known: {', '.join(_KNOWN)}) — skipping."
            )
    return providers
