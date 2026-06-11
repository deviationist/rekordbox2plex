from rekordbox2plex.utils.pairing import walk_pairs

LOSSY = (".mp3",)
LOSSLESS = (".aiff", ".aif")


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_pairs_unmatched_and_ambiguous(tmp_path):
    _touch(tmp_path / "A/song.mp3")
    _touch(tmp_path / "A/song.aiff")  # clean pair
    _touch(tmp_path / "A/orphan.mp3")  # no lossless sibling
    _touch(tmp_path / "B/dup.mp3")
    _touch(tmp_path / "B/dup.aiff")
    _touch(tmp_path / "B/dup.aif")  # ambiguous: two lossless siblings

    pairs, unmatched, ambiguous = walk_pairs(str(tmp_path), LOSSY, LOSSLESS)

    assert pairs == [(str(tmp_path / "A/song.mp3"), str(tmp_path / "A/song.aiff"))]
    assert unmatched == [str(tmp_path / "A/orphan.mp3")]
    assert len(ambiguous) == 1
    assert ">1 lossless sibling" in ambiguous[0][1]


def test_case_sensitivity(tmp_path):
    _touch(tmp_path / "Song.mp3")
    _touch(tmp_path / "song.aiff")

    pairs, unmatched, _ = walk_pairs(str(tmp_path), LOSSY, LOSSLESS, ignore_case=False)
    assert pairs == [] and len(unmatched) == 1

    pairs, unmatched, _ = walk_pairs(str(tmp_path), LOSSY, LOSSLESS, ignore_case=True)
    assert len(pairs) == 1 and unmatched == []


def test_non_configured_extensions_are_ignored(tmp_path):
    _touch(tmp_path / "t.mp3")
    _touch(tmp_path / "t.flac")  # not in LOSSLESS → not a sibling

    pairs, unmatched, ambiguous = walk_pairs(str(tmp_path), LOSSY, LOSSLESS)
    assert pairs == [] and not ambiguous
    assert unmatched == [str(tmp_path / "t.mp3")]
