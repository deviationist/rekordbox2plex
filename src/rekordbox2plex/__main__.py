__import__('dotenv').load_dotenv()
from .actions.TrackSync import TrackSync
from .utils.logger import init_logger
from .utils.helpers import determine_sync_targets, parse_script_arguments
from .actions.PlaylistSync import PlaylistSync
from .actions.ArtworkSync import ArtworkSync
from .rekordbox.RekordboxDB import setup_db_connection

def main():
    setup_db_connection()
    args = parse_script_arguments()
    init_logger(args)
    sync = determine_sync_targets(args)
    if "tracks" in sync:
        TrackSync().sync()
    if "playlists" in sync:
        PlaylistSync().sync()
    if "artwork" in sync:
        ArtworkSync().sync()
