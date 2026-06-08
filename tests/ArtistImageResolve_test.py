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


class _NameStub:
    """Provider that 'has' an artist only for the exact names in its map."""

    def __init__(self, name, mapping):
        self.name = name
        self.requires_mbid = False
        self._map = mapping  # {artist_name: url}

    def find(self, artist_name, mbid=None, accept_names=None):
        url = self._map.get(artist_name)
        if url:
            return ProviderResult.hit(ArtistImage(url=url, source=self.name))
        return ProviderResult.miss()


def _action(providers, collab_mode="skip", ambiguous_seps=None, min_seg_len=2):
    a = ArtistImageSync.__new__(ArtistImageSync)  # bypass __init__/config/network
    a.providers = providers
    a.collab_mode = collab_mode
    a.ambiguous_seps = ambiguous_seps or []
    a.collab_min_score = 95
    a.collab_min_seg_len = min_seg_len
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


# --- resilient collab splitting (last resort, &/+ opt-in) ---------------------


def test_collab_ambiguous_split_when_whole_misses(monkeypatch):
    # Whole "Lane 8 & Kasablanca" not known; the two members are → collage.
    prov = _NameStub("p", {"Lane 8": "u_lane8", "Kasablanca": "u_kasa"})
    a = _action([prov], collab_mode="collage", ambiguous_seps=["&", "+"])
    monkeypatch.setattr(ais_mod, "is_unusable_url", lambda *a2, **k: False)
    img, _ = a._resolve(types.SimpleNamespace(title="Lane 8 & Kasablanca"))
    assert img is not None and img.source == "collage"
    assert img.members == ["u_lane8", "u_kasa"]


def test_collab_keeps_whole_ampersand_artist(monkeypatch):
    # "Above & Beyond" is a real artist → resolved whole, never split.
    prov = _NameStub("p", {"Above & Beyond": "u_ab"})
    a = _action([prov], collab_mode="collage", ambiguous_seps=["&", "+"])
    monkeypatch.setattr(ais_mod, "is_unusable_url", lambda *a2, **k: False)
    img, _ = a._resolve(types.SimpleNamespace(title="Above & Beyond"))
    assert img is not None and img.url == "u_ab" and img.source == "p"


def test_collab_ambiguous_disabled_without_extra_seps(monkeypatch):
    # No configured ambiguous separators → no split, stays a no-match.
    prov = _NameStub("p", {"Lane 8": "u_lane8", "Kasablanca": "u_kasa"})
    a = _action([prov], collab_mode="collage", ambiguous_seps=[])
    monkeypatch.setattr(ais_mod, "is_unusable_url", lambda *a2, **k: False)
    img, _ = a._resolve(types.SimpleNamespace(title="Lane 8 & Kasablanca"))
    assert img is None


def test_collab_min_segment_len_skips_short_fragment(monkeypatch):
    # min_seg_len=3 drops "Bz" but keeps "Cumber".
    prov = _NameStub("p", {"Bz": "u_bz", "Cumber": "u_cumber"})
    a = _action([prov], collab_mode="collage", ambiguous_seps=["&"], min_seg_len=3)
    monkeypatch.setattr(ais_mod, "is_unusable_url", lambda *a2, **k: False)
    img, _ = a._resolve(types.SimpleNamespace(title="Bz & Cumber"))
    assert img is not None and img.members == ["u_cumber"]
