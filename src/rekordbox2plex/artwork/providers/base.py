import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set


def normalize_name(s: Optional[str]) -> str:
    """Normalize an artist name for matching: drop a trailing Discogs
    disambiguation suffix ("Artist (2)"), collapse whitespace, casefold."""
    s = re.sub(r"\s*\(\d+\)\s*$", "", s or "")
    return re.sub(r"\s+", " ", s.strip()).casefold()


def accept_set(
    artist_name: str, accept_names: Optional[Iterable[str]] = None
) -> Set[str]:
    """The set of normalized names a name-based hit is allowed to match."""
    names = list(accept_names) if accept_names else [artist_name]
    return {normalize_name(n) for n in names if n}


@dataclass
class ArtistImage:
    """A resolved artist image: where to fetch it and which provider/kind it is."""

    url: str
    source: str  # provider name, e.g. "discogs", "theaudiodb", "collage"
    kind: str = "thumb"  # "thumb" (square portrait) | "background" (fanart)
    matched_name: Optional[str] = None  # the provider-side name we matched (audit)
    # For collab "collage" results: member portrait URLs to composite at upload
    # time (url stays empty — there's no single source image).
    members: Optional[List[str]] = None


# Outcome statuses for observability (why a provider did/didn't return art).
HIT = "hit"
MISS = "miss"  # queried fine, no image for this artist
RATE_LIMITED = "rate_limited"  # HTTP 429 / throttled
ERROR = "error"  # network/parse failure
SKIPPED = "skipped"  # provider couldn't even try (e.g. no MBID, no key)


@dataclass
class ProviderResult:
    """What a provider did for one artist — image plus a status/detail so the
    caller can report *why* it failed, not just that it did."""

    status: str = MISS
    image: Optional[ArtistImage] = None
    detail: str = ""

    @classmethod
    def hit(cls, image: ArtistImage) -> "ProviderResult":
        return cls(status=HIT, image=image)

    @classmethod
    def miss(cls, detail: str = "") -> "ProviderResult":
        return cls(status=MISS, detail=detail)

    @classmethod
    def rate_limited(cls, detail: str = "HTTP 429") -> "ProviderResult":
        return cls(status=RATE_LIMITED, detail=detail)

    @classmethod
    def error(cls, detail: str) -> "ProviderResult":
        return cls(status=ERROR, detail=detail)

    @classmethod
    def skipped(cls, detail: str) -> "ProviderResult":
        return cls(status=SKIPPED, detail=detail)


class ArtistImageProvider(ABC):
    """A single artist-image source ("driver"), keyed by artist name and/or MBID.

    Implementations never raise — they return a ProviderResult whose status
    explains the outcome (hit/miss/rate_limited/error/skipped). The MBID and the
    set of acceptable names (``accept_names`` — the local tag plus Plex's canonical
    name) are resolved once by the action and passed in. Name-based providers must
    verify a result's name against ``accept_names`` to avoid fuzzy mismatches; MBID
    lookups are authoritative and skip name verification."""

    #: short identifier used in config (PLEX_ARTIST_IMAGE_PROVIDERS) and logs
    name: str = "base"
    #: True when the provider can ONLY work with an MBID (e.g. fanart.tv).
    requires_mbid: bool = False

    @abstractmethod
    def find(
        self,
        artist_name: str,
        mbid: Optional[str] = None,
        accept_names: Optional[Iterable[str]] = None,
    ) -> ProviderResult: ...
