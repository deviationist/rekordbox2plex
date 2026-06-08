import types

from rekordbox2plex.artwork.mbid import PlexMbidResolver
from rekordbox2plex.artwork import musicbrainz as mb_mod
from rekordbox2plex.artwork.musicbrainz import MusicBrainzResolver
from rekordbox2plex.artwork.providers import (
    DiscogsProvider,
    FanartTvProvider,
    TheAudioDBProvider,
)
from rekordbox2plex.artwork.providers import discogs as discogs_mod
from rekordbox2plex.artwork.providers import fanarttv as fanart_mod
from rekordbox2plex.artwork.providers import theaudiodb as tadb_mod
from rekordbox2plex.artwork.providers.base import (
    ERROR,
    HIT,
    MISS,
    RATE_LIMITED,
    SKIPPED,
)
from rekordbox2plex.artwork.registry import build_providers


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _patch_get(monkeypatch, module, fn):
    monkeypatch.setattr(module.requests, "get", fn)


# --- TheAudioDB ---------------------------------------------------------------


def test_theaudiodb_returns_thumb(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return FakeResp(
            {
                "artists": [
                    {"strArtist": "Ben Böhmer", "strArtistThumb": "http://i/t.jpg"}
                ]
            }
        )

    _patch_get(monkeypatch, tadb_mod, fake_get)
    r = TheAudioDBProvider("2").find("Ben Böhmer")
    assert r.status == HIT and r.image is not None
    assert r.image.url == "http://i/t.jpg"
    assert r.image.source == "theaudiodb" and r.image.kind == "thumb"


def test_theaudiodb_thumb_only_no_fanart_fallback(monkeypatch):
    # Only a landscape fanart, no portrait thumb → miss (posters want portraits).
    def fake_get(url, params=None, timeout=None):
        return FakeResp(
            {"artists": [{"strArtist": "X", "strArtistFanart": "http://i/bg.jpg"}]}
        )

    _patch_get(monkeypatch, tadb_mod, fake_get)
    r = TheAudioDBProvider().find("X")
    assert r.status == MISS and r.image is None


def test_theaudiodb_name_search_rejects_mismatch(monkeypatch):
    # Name search returns a different artist → reject (no fuzzy false positive).
    def fake_get(url, params=None, timeout=None):
        return FakeResp(
            {"artists": [{"strArtist": "Someone Else", "strArtistThumb": "http://i/x"}]}
        )

    _patch_get(monkeypatch, tadb_mod, fake_get)
    r = TheAudioDBProvider().find("10bz")  # no mbid → name search path
    assert r.status == MISS and r.image is None


def test_theaudiodb_prefers_mbid_endpoint(monkeypatch):
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen["url"] = url
        return FakeResp({"artists": [{"strArtistThumb": "http://img/by-mb.jpg"}]})

    _patch_get(monkeypatch, tadb_mod, fake_get)
    r = TheAudioDBProvider().find("X", mbid="mbid-123")
    assert r.image.url == "http://img/by-mb.jpg"
    assert "artist-mb.php" in seen["url"]  # used the MBID endpoint, not search


def test_theaudiodb_miss_rate_limit_and_error(monkeypatch):
    _patch_get(monkeypatch, tadb_mod, lambda *a, **k: FakeResp({"artists": None}))
    r = TheAudioDBProvider().find("nobody")
    assert r.status == MISS and r.image is None

    _patch_get(monkeypatch, tadb_mod, lambda *a, **k: FakeResp({}, status=429))
    assert TheAudioDBProvider().find("x").status == RATE_LIMITED

    def boom(*a, **k):
        raise tadb_mod.requests.RequestException("network")

    _patch_get(monkeypatch, tadb_mod, boom)
    r = TheAudioDBProvider().find("x")  # never raises
    assert r.status == ERROR and r.image is None


# --- fanart.tv ----------------------------------------------------------------


def test_fanarttv_skips_without_mbid_or_key():
    assert FanartTvProvider("key").find("X", mbid=None).status == SKIPPED
    assert FanartTvProvider("").find("X", mbid="abc").status == SKIPPED


def test_fanarttv_returns_thumb(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return FakeResp({"artistthumb": [{"url": "http://fa/thumb.jpg"}]})

    _patch_get(monkeypatch, fanart_mod, fake_get)
    r = FanartTvProvider("key").find("X", mbid="mbid-123")
    assert r.image.url == "http://fa/thumb.jpg" and r.image.source == "fanarttv"


def test_fanarttv_404_is_miss(monkeypatch):
    _patch_get(monkeypatch, fanart_mod, lambda *a, **k: FakeResp({}, status=404))
    r = FanartTvProvider("key").find("X", mbid="mbid")
    assert r.status == MISS and r.image is None


# --- Discogs ------------------------------------------------------------------


def test_discogs_skips_without_credentials():
    assert DiscogsProvider("ua").find("X").status == SKIPPED


def test_discogs_returns_cover_image(monkeypatch):
    seen = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen["params"] = params
        return FakeResp(
            {
                "results": [
                    {
                        "title": "Boris Brejcha",
                        "cover_image": "http://dc/a.jpg",
                        "thumb": "http://dc/t.jpg",
                    }
                ]
            }
        )

    monkeypatch.setattr(discogs_mod.time, "sleep", lambda s: None)
    _patch_get(monkeypatch, discogs_mod, fake_get)
    r = DiscogsProvider("ua", token="tok").find("Boris Brejcha")
    assert r.status == HIT and r.image.url == "http://dc/a.jpg"
    assert r.image.source == "discogs" and r.image.matched_name == "Boris Brejcha"
    assert seen["params"]["token"] == "tok"  # token auth used


def test_discogs_rejects_wrong_name(monkeypatch):
    # Top result is a different artist — must be rejected, not blindly accepted.
    monkeypatch.setattr(discogs_mod.time, "sleep", lambda s: None)
    _patch_get(
        monkeypatch,
        discogs_mod,
        lambda *a, **k: FakeResp(
            {"results": [{"title": "Tom Talomaa", "cover_image": "http://dc/x.jpg"}]}
        ),
    )
    r = DiscogsProvider("ua", token="t").find("10bz")
    assert r.status == MISS and r.image is None


def test_discogs_accepts_disambiguation_and_canonical(monkeypatch):
    monkeypatch.setattr(discogs_mod.time, "sleep", lambda s: None)
    # "1991 (2)" disambiguation should still match "1991".
    _patch_get(
        monkeypatch,
        discogs_mod,
        lambda *a, **k: FakeResp(
            {"results": [{"title": "1991 (2)", "cover_image": "http://dc/y.jpg"}]}
        ),
    )
    assert DiscogsProvider("ua", token="t").find("1991").status == HIT

    # A result matching Plex's canonical name (not the local tag) is accepted.
    _patch_get(
        monkeypatch,
        discogs_mod,
        lambda *a, **k: FakeResp(
            {"results": [{"title": "Canonical Name", "cover_image": "http://dc/z.jpg"}]}
        ),
    )
    r = DiscogsProvider("ua", token="t").find(
        "Local Tag", accept_names=["Local Tag", "Canonical Name"]
    )
    assert r.status == HIT and r.image.matched_name == "Canonical Name"


def test_discogs_picks_matching_result_not_first(monkeypatch):
    # First result is wrong, second matches — provider should scan past [0].
    monkeypatch.setattr(discogs_mod.time, "sleep", lambda s: None)
    _patch_get(
        monkeypatch,
        discogs_mod,
        lambda *a, **k: FakeResp(
            {
                "results": [
                    {"title": "Wrong Artist", "cover_image": "http://dc/wrong.jpg"},
                    {"title": "Right One", "cover_image": "http://dc/right.jpg"},
                ]
            }
        ),
    )
    r = DiscogsProvider("ua", token="t").find("Right One")
    assert r.status == HIT and r.image.url == "http://dc/right.jpg"


def test_discogs_uses_key_secret_when_no_token(monkeypatch):
    seen = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen["params"] = params
        return FakeResp({"results": [{"title": "X", "cover_image": "http://dc/a.jpg"}]})

    monkeypatch.setattr(discogs_mod.time, "sleep", lambda s: None)
    _patch_get(monkeypatch, discogs_mod, fake_get)
    r = DiscogsProvider("ua", key="K", secret="S").find("X")
    assert r.status == HIT
    assert seen["params"]["key"] == "K" and seen["params"]["secret"] == "S"
    assert "token" not in seen["params"]


def test_discogs_skips_spacer_and_rate_limit(monkeypatch):
    monkeypatch.setattr(discogs_mod.time, "sleep", lambda s: None)
    _patch_get(
        monkeypatch,
        discogs_mod,
        lambda *a, **k: FakeResp(
            {"results": [{"title": "X", "cover_image": "x/spacer.gif"}]}
        ),
    )
    assert DiscogsProvider("ua", token="t").find("X").status == MISS

    _patch_get(monkeypatch, discogs_mod, lambda *a, **k: FakeResp({}, status=429))
    assert DiscogsProvider("ua", token="t").find("X").status == RATE_LIMITED


# --- Plex MBID resolver -------------------------------------------------------


def test_plex_mbid_resolver_takes_top_confident():
    m1 = types.SimpleNamespace(guid="mbid://abc-123", score=100)
    m2 = types.SimpleNamespace(guid="mbid://def-456", score=50)
    artist = types.SimpleNamespace(title="X", matches=lambda agent=None: [m1, m2])
    assert PlexMbidResolver().mbid_for(artist) == "abc-123"


def test_plex_mbid_resolver_rejects_low_score_and_failures():
    low = types.SimpleNamespace(guid="mbid://x", score=40)
    assert (
        PlexMbidResolver().mbid_for(
            types.SimpleNamespace(title="Y", matches=lambda agent=None: [low])
        )
        is None
    )
    assert PlexMbidResolver().mbid_for(None) is None

    def boom(agent=None):
        raise RuntimeError("agent down")

    assert (
        PlexMbidResolver().mbid_for(types.SimpleNamespace(title="Z", matches=boom))
        is None
    )


# --- MusicBrainz resolver -----------------------------------------------------


def test_musicbrainz_confident_match(monkeypatch):
    monkeypatch.setattr(mb_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        mb_mod.requests,
        "get",
        lambda *a, **k: FakeResp({"artists": [{"id": "MBID-1", "score": 100}]}),
    )
    r = MusicBrainzResolver("ua")
    assert r.mbid_for("Ben Böhmer") == "MBID-1"
    assert r.mbid_for("Ben Böhmer") == "MBID-1"  # cached


def test_musicbrainz_low_score_is_none(monkeypatch):
    monkeypatch.setattr(mb_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        mb_mod.requests,
        "get",
        lambda *a, **k: FakeResp({"artists": [{"id": "MBID-1", "score": 40}]}),
    )
    assert MusicBrainzResolver("ua").mbid_for("Fuzzy") is None


# --- registry -----------------------------------------------------------------


def test_registry_builds_in_order_and_skips_unknown(monkeypatch):
    monkeypatch.delenv("FANARTTV_API_KEY", raising=False)
    provs = build_providers(["theaudiodb", "bogus", "fanarttv"])
    # theaudiodb built; bogus skipped; fanarttv skipped (no key)
    assert [p.name for p in provs] == ["theaudiodb"]


def test_registry_includes_fanarttv_with_key(monkeypatch):
    monkeypatch.setenv("FANARTTV_API_KEY", "k")
    provs = build_providers(["fanarttv"])
    assert [p.name for p in provs] == ["fanarttv"]


def test_registry_discogs_needs_credentials(monkeypatch):
    for var in ("DISCOGS_TOKEN", "DISCOGS_KEY", "DISCOGS_SECRET"):
        monkeypatch.delenv(var, raising=False)
    assert build_providers(["discogs"]) == []  # no creds → skipped

    monkeypatch.setenv("DISCOGS_TOKEN", "tok")
    provs = build_providers(["discogs", "theaudiodb"])
    assert [p.name for p in provs] == ["discogs", "theaudiodb"]
