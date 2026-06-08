import hashlib
import io

from PIL import Image

from rekordbox2plex.artwork import placeholder as ph_mod
from rekordbox2plex.artwork.providers import (
    BandcampProvider,
    DeezerProvider,
    SpotifyProvider,
)
from rekordbox2plex.artwork.providers import bandcamp as bandcamp_mod
from rekordbox2plex.artwork.providers import deezer as deezer_mod
from rekordbox2plex.artwork.providers import spotify as spotify_mod
from rekordbox2plex.artwork.providers.base import HIT, MISS, RATE_LIMITED, SKIPPED
from rekordbox2plex.artwork.registry import build_providers


class FakeResp:
    def __init__(self, payload, status=200, content=b""):
        self._payload = payload
        self.status_code = status
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _png(color, size=(80, 80)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


def test_is_placeholder_bytes_scoped_per_provider(monkeypatch):
    data = b"pretend-this-is-the-grey-silhouette"
    monkeypatch.setattr(
        ph_mod, "_PLACEHOLDER_MD5", {"deezer": {hashlib.md5(data).hexdigest()}}
    )
    # matches only when checked against the owning provider
    assert ph_mod.is_placeholder_bytes(data, "deezer") is True
    assert ph_mod.is_placeholder_bytes(data, "spotify") is False  # not Spotify's
    assert ph_mod.is_placeholder_bytes(data) is True  # None ⇒ union of all
    assert ph_mod.is_placeholder_bytes(b"a real image", "deezer") is False


def test_is_near_uniform_bytes():
    assert ph_mod.is_near_uniform_bytes(_png((0, 0, 0))) is True  # solid black
    assert ph_mod.is_near_uniform_bytes(_png((255, 255, 255))) is True  # solid white
    # a two-tone image (real content) is not uniform
    img = Image.new("RGB", (80, 80), (0, 0, 0))
    img.paste((200, 180, 160), (0, 0, 40, 80))
    b = io.BytesIO()
    img.save(b, "PNG")
    assert ph_mod.is_near_uniform_bytes(b.getvalue()) is False


# --- Deezer -------------------------------------------------------------------


def test_deezer_returns_verified_picture(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResp(
            {"data": [{"name": "Boris Brejcha", "picture_xl": "http://dz/xl.jpg"}]}
        )

    monkeypatch.setattr(deezer_mod.requests, "get", fake_get)
    r = DeezerProvider().find("Boris Brejcha")
    assert r.status == HIT and r.image.url == "http://dz/xl.jpg"
    assert r.image.source == "deezer"


def test_deezer_rejects_wrong_name(monkeypatch):
    monkeypatch.setattr(
        deezer_mod.requests,
        "get",
        lambda *a, **k: FakeResp({"data": [{"name": "Other", "picture_xl": "x"}]}),
    )
    assert DeezerProvider().find("10bz").status == MISS


def test_deezer_skips_empty_id_placeholder(monkeypatch):
    # Deezer's no-photo silhouette comes back as an empty-id URL (".../artist//...")
    monkeypatch.setattr(
        deezer_mod.requests,
        "get",
        lambda *a, **k: FakeResp(
            {
                "data": [
                    {
                        "name": "DM Binxter",
                        "picture_xl": "https://cdn-images.dzcdn.net/images/artist//1000x1000-000000-80-0-0.jpg",
                    }
                ]
            }
        ),
    )
    # name matched but the only picture is the empty-id placeholder → miss
    assert DeezerProvider().find("DM Binxter").status == MISS


def test_deezer_rate_limit(monkeypatch):
    monkeypatch.setattr(
        deezer_mod.requests, "get", lambda *a, **k: FakeResp({}, status=429)
    )
    assert DeezerProvider().find("X").status == RATE_LIMITED


# --- Spotify ------------------------------------------------------------------


def test_spotify_skips_without_credentials():
    assert SpotifyProvider(None, None).find("X").status == SKIPPED


def test_spotify_returns_verified_image(monkeypatch):
    monkeypatch.setattr(
        spotify_mod.requests,
        "post",
        lambda *a, **k: FakeResp({"access_token": "tok", "expires_in": 3600}),
    )

    def fake_get(url, params=None, headers=None, timeout=None):
        assert headers["Authorization"] == "Bearer tok"
        return FakeResp(
            {
                "artists": {
                    "items": [
                        {"name": "Ben Böhmer", "images": [{"url": "http://sp/0.jpg"}]}
                    ]
                }
            }
        )

    monkeypatch.setattr(spotify_mod.requests, "get", fake_get)
    r = SpotifyProvider("id", "sec").find("Ben Böhmer")
    assert r.status == HIT and r.image.url == "http://sp/0.jpg"
    assert r.image.source == "spotify"


def test_spotify_rejects_wrong_name(monkeypatch):
    monkeypatch.setattr(
        spotify_mod.requests,
        "post",
        lambda *a, **k: FakeResp({"access_token": "t", "expires_in": 3600}),
    )
    monkeypatch.setattr(
        spotify_mod.requests,
        "get",
        lambda *a, **k: FakeResp(
            {"artists": {"items": [{"name": "Someone Else", "images": [{"url": "x"}]}]}}
        ),
    )
    assert SpotifyProvider("id", "sec").find("10bz").status == MISS


# --- Bandcamp -----------------------------------------------------------------


def _bc_results(results):
    return FakeResp({"auto": {"results": results}})


def test_bandcamp_returns_full_res_band_photo(monkeypatch):
    monkeypatch.setattr(
        bandcamp_mod.cffi,
        "post",
        lambda *a, **k: _bc_results(
            [
                {
                    "type": "b",
                    "name": "A/B Sides",
                    "img": "https://f4.bcbits.com/img/0041637995_23.jpg",
                }
            ]
        ),
    )
    r = BandcampProvider().find("A/B Sides")
    assert r.status == HIT and r.image.source == "bandcamp"
    # search thumbnail (_23) upgraded to the full 1200x1200 band photo (_10)
    assert r.image.url == "https://f4.bcbits.com/img/0041637995_10.jpg"


def test_bandcamp_rejects_wrong_name(monkeypatch):
    monkeypatch.setattr(
        bandcamp_mod.cffi,
        "post",
        lambda *a, **k: _bc_results(
            [{"type": "b", "name": "Some Other Band", "img": "x_23.jpg"}]
        ),
    )
    assert BandcampProvider().find("A/B Sides").status == MISS


def test_bandcamp_rate_limit(monkeypatch):
    monkeypatch.setattr(
        bandcamp_mod.cffi, "post", lambda *a, **k: FakeResp({}, status=429)
    )
    assert BandcampProvider().find("X").status == RATE_LIMITED


# --- registry -----------------------------------------------------------------


def test_registry_deezer_always_built_spotify_needs_creds(monkeypatch):
    for v in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"):
        monkeypatch.delenv(v, raising=False)
    provs = build_providers(["deezer", "spotify"])
    assert [p.name for p in provs] == ["deezer"]  # spotify skipped (no creds)

    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "sec")
    provs = build_providers(["deezer", "spotify"])
    assert [p.name for p in provs] == ["deezer", "spotify"]
