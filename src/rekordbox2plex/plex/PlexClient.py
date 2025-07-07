from plexapi.server import PlexServer
import os

def plexapi_client() -> PlexServer:
    server = PlexClient().server
    if server is None:
        raise Exception("Could not initialize Plex SDK")
    return server

class PlexClient:
    _instance = None
    _server = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PlexClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._server is None:
            plex_url = os.getenv("PLEX_URL")
            plex_token = os.getenv("PLEX_TOKEN")
            self._server = PlexServer(plex_url, plex_token)

    def get_server(self):
        return self._server

    @property
    def server(self):
        return self._server
