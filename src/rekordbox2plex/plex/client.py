from plexapi.server import PlexServer
import os

PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")

def main():
    return PlexServer(PLEX_URL, PLEX_TOKEN)
