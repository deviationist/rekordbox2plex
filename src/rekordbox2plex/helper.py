def build_track_string(plex_track) -> str:
    return f'"{plex_track["title"]}" by "{plex_track["track_artist"]}"'
