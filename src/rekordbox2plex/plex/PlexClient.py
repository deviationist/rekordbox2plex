import os
from typing import Optional, Type
from plexapi.server import PlexServer  # Ensure this is imported

def plexapi_client() -> PlexServer:
    server = PlexClient().server
    if server is None:
        raise Exception("Could not initialize Plex SDK")
    return server

class PlexClient:
    _instance: Optional["PlexClient"] = None
    _server: Optional[PlexServer] = None

    def __new__(cls: Type["PlexClient"]) -> "PlexClient":
        if cls._instance is None:
            cls._instance = super(PlexClient, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._server is None:
            plex_url = os.getenv("PLEX_URL")
            plex_token = os.getenv("PLEX_TOKEN")
            if not plex_url or not plex_token:
                raise Exception('Could not initialize Plex API client. Please check that environment variable "PLEX_URL" and "PLEX_TOKEN" is set.')
            self._server = PlexServer(plex_url, plex_token)

    def get_server(self) -> PlexServer:
        return self._server

    @property
    def server(self) -> PlexServer:
        return self._server
