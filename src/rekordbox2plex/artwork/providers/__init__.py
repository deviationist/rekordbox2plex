from .base import ArtistImage, ArtistImageProvider, ProviderResult
from .deezer import DeezerProvider
from .discogs import DiscogsProvider
from .fanarttv import FanartTvProvider
from .spotify import SpotifyProvider
from .theaudiodb import TheAudioDBProvider

__all__ = [
    "ArtistImage",
    "ArtistImageProvider",
    "ProviderResult",
    "TheAudioDBProvider",
    "FanartTvProvider",
    "DiscogsProvider",
    "DeezerProvider",
    "SpotifyProvider",
]
