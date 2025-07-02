class AudioMetadataMapper:
    FORCE_UPDATE = True
    def __init__(self, plex_track, rb_item):
        rb_track, rb_artist, rb_artwork, rb_album, rb_album_artist = rb_item
        self.rb_track = rb_track
        self.rb_artist = rb_artist
        self.rb_artwork = rb_artwork
        self.rb_album = rb_album
        self.rb_album_artist = rb_album_artist
        self.plex_track = plex_track
        self.edits = {}

    def updateTrackTitle(self):
        trackTitle = self.rb_track.get("Title", "") if self.rb_track else ""
        self.edits["title.locked"] = 1
        self.edits["title.value"] = trackTitle

    def updateTrackArtist(self):
        artistName = self.rb_artist.get("Name", "") if self.rb_artist else ""
        self.edits["originalTitle.value"] = artistName
        self.edits["originalTitle.locked"] = 1

    def updateAlbumArtist(self):
        albumArtistName = self.rb_album.get("Name", "") if self.rb_album else ""
        self.edits["artist.title.value"] = albumArtistName

    def updateAlbum(self):
        albumName = self.rb_album.get("Name", "") if self.rb_album else ""
        self.edits["album.title.value"] = albumName

    def transfer(self):
        self.updateTrackTitle()
        self.updateTrackArtist()
        self.updateAlbumArtist()
        self.updateAlbum()
        return self

    def save(self):
        self.plex_track["track_object"].edit(**self.edits)
        self.plex_track["track_object"].reload()
