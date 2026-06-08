"""The action validates every provider's image centrally (placeholder / blank /
single-color → non-match), uniformly across all sources, then falls through."""

import types

from rekordbox2plex.actions import ArtistImageSync as ais_mod
from rekordbox2plex.actions.ArtistImageSync import ArtistImageSync
from rekordbox2plex.artwork.providers.base import ArtistImage, ProviderResult


class _StubProvider:
    def __init__(self, name, image):
        self.name = name
        self.requires_mbid = False
        self._image = image

    def find(self, artist_name, mbid=None, accept_names=None):
        return ProviderResult.hit(self._image) if self._image else ProviderResult.miss()


def _action(providers):
    a = ArtistImageSync.__new__(ArtistImageSync)  # bypass __init__/config/network
    a.providers = providers
    a.collab_mode = "skip"
    a._mb = None
    a.plex_mbid = types.SimpleNamespace(match=lambda artist: None)
    return a


def test_resolve_skips_unusable_image_and_uses_next_source(monkeypatch):
    bad = ArtistImage(url="http://bad/black.jpg", source="p1")
    good = ArtistImage(url="http://good/portrait.jpg", source="p2")
    a = _action([_StubProvider("p1", bad), _StubProvider("p2", good)])
    # p1's image is unusable (e.g. blank/placeholder), p2's is fine.
    monkeypatch.setattr(
        ais_mod,
        "is_unusable_url",
        lambda url, *args, **kw: url == "http://bad/black.jpg",
    )
    img, attempts = a._resolve(types.SimpleNamespace(title="X"))
    assert img is good
    # p1 recorded as 'unusable', p2 as a hit
    assert ("p1", "unusable", "http://bad/black.jpg") in attempts
    assert any(w == "p2" and s == "hit" for w, s, _ in attempts)


def test_resolve_all_unusable_is_no_match(monkeypatch):
    a = _action([_StubProvider("p1", ArtistImage(url="u1", source="p1"))])
    monkeypatch.setattr(ais_mod, "is_unusable_url", lambda *a2, **k: True)
    img, _ = a._resolve(types.SimpleNamespace(title="X"))
    assert img is None


def test_resolve_member_skips_unusable(monkeypatch):
    a = _action([_StubProvider("p1", ArtistImage(url="u1", source="p1"))])
    monkeypatch.setattr(ais_mod, "is_unusable_url", lambda *a2, **k: True)
    assert a._resolve_member("Some Member") is None
