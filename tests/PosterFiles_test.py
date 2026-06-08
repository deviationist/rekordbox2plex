from rekordbox2plex.plex.poster_files import (
    bundle_posters_dir,
    metadata_dir_from_db_path,
    poster_file_path,
)

# Real values verified on disk for the "10bz" artist (id 28859):
#   guid tv.plex.agents.none://28859  -> sha1 6129e89ba0889154824fc4e7b1e7ad111f0e2cd0
#   bundle Artists/6/129e89ba0889154824fc4e7b1e7ad111f0e2cd0.bundle/Uploads/posters/<hash>
_GUID = "tv.plex.agents.none://28859"
_SHA = "6129e89ba0889154824fc4e7b1e7ad111f0e2cd0"


def test_metadata_dir_from_db_path():
    db = (
        "/x/Plex Media Server/Plug-in Support/Databases/"
        "com.plexapp.plugins.library.db"
    )
    assert metadata_dir_from_db_path(db) == "/x/Plex Media Server/Metadata"


def test_bundle_posters_dir_artist():
    p = bundle_posters_dir("/META", 8, _GUID)
    assert p == f"/META/Artists/{_SHA[0]}/{_SHA[1:]}.bundle/Uploads/posters"


def test_bundle_posters_dir_album_uses_albums_dir():
    p = bundle_posters_dir("/META", 9, "tv.plex.agents.none://31213")
    assert "/Albums/" in p and p.endswith(".bundle/Uploads/posters")


def test_bundle_posters_dir_unsupported_type_or_empty_guid():
    assert bundle_posters_dir("/META", 10, _GUID) is None  # track: unsupported
    assert bundle_posters_dir("/META", 8, "") is None


def test_poster_file_path_from_upload_url():
    url = "upload://posters/dbcf4003c0de6dbe3ec66a986d2ee20f4e3eaea1"
    p = poster_file_path("/META", 8, _GUID, url)
    assert p == (
        f"/META/Artists/{_SHA[0]}/{_SHA[1:]}.bundle/Uploads/posters/"
        "dbcf4003c0de6dbe3ec66a986d2ee20f4e3eaea1"
    )


def test_poster_file_path_non_upload_is_none():
    assert poster_file_path("/META", 8, _GUID, "metadata://thumbs/x") is None
    assert poster_file_path("/META", 8, _GUID, "") is None
