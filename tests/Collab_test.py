import io

from PIL import Image

from rekordbox2plex.artwork import collage as collage_mod
from rekordbox2plex.artwork.collab import split_collab


# --- split_collab -------------------------------------------------------------


def test_split_collab_splits_comma_and_feat():
    assert split_collab("A*S*Y*S, Kai Tracid, Tom Wax") == [
        "A*S*Y*S",
        "Kai Tracid",
        "Tom Wax",
    ]
    assert split_collab("Above & Beyond, OceanLab") == ["Above & Beyond", "OceanLab"]
    assert split_collab("Artist feat. Other") == ["Artist", "Other"]
    assert split_collab("Artist ft. Other") == ["Artist", "Other"]


def test_split_collab_leaves_single_names_intact():
    # '&', '/', 'x' are NOT split — these are single artists, not collabs.
    for s in ["Above & Beyond", "A/B Sides", "AC/DC", "Solo Artist", "", "  "]:
        assert split_collab(s) == []


# --- compose_strips -----------------------------------------------------------


def _png_bytes(color):
    # Non-uniform on purpose — a solid color is now (correctly) rejected as blank.
    im = Image.new("RGB", (120, 90), color)
    contrast = (0, 0, 0) if color != (0, 0, 0) else (255, 255, 255)
    im.paste(contrast, (0, 0, 50, 45))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


class _FakeResp:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


def test_compose_strips_creates_square_poster(tmp_path, monkeypatch):
    data = {"u1": _png_bytes((200, 0, 0)), "u2": _png_bytes((0, 200, 0))}
    monkeypatch.setattr(collage_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        collage_mod.requests,
        "get",
        lambda u, timeout=None, headers=None: _FakeResp(data[u]),
    )
    out = tmp_path / "c.jpg"
    assert collage_mod.compose_strips(["u1", "u2"], str(out), size=200) is True
    assert out.exists()
    assert Image.open(out).size == (200, 200)


def test_compose_strips_skips_failures_but_uses_the_rest(tmp_path, monkeypatch):
    good = _png_bytes((0, 0, 200))

    def get(u, timeout=None, headers=None):
        if u == "bad":
            raise collage_mod.requests.RequestException("boom")
        return _FakeResp(good)

    monkeypatch.setattr(collage_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(collage_mod.requests, "get", get)
    out = tmp_path / "c.jpg"
    assert collage_mod.compose_strips(["bad", "u2"], str(out), size=150) is True
    assert Image.open(out).size == (150, 150)


def test_compose_strips_skips_placeholder_panel(tmp_path, monkeypatch):
    # A member whose image is the known placeholder must not become a panel.
    good = _png_bytes((10, 120, 200))
    monkeypatch.setattr(collage_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        collage_mod.requests,
        "get",
        lambda u, timeout=None, headers=None: _FakeResp(
            b"PLACEHOLDER" if u == "ph" else good
        ),
    )
    monkeypatch.setattr(collage_mod, "is_unusable_bytes", lambda c: c == b"PLACEHOLDER")
    out = tmp_path / "c.jpg"
    assert collage_mod.compose_strips(["ph", "real"], str(out), size=150) is True
    assert Image.open(out).size == (150, 150)  # built from the one real member


def test_compose_strips_all_fail_returns_false(tmp_path, monkeypatch):
    def boom(u, timeout=None, headers=None):
        raise collage_mod.requests.RequestException("x")

    monkeypatch.setattr(collage_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(collage_mod.requests, "get", boom)
    out = tmp_path / "c.jpg"
    assert collage_mod.compose_strips(["u1"], str(out)) is False
    assert not out.exists()
