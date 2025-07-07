import dotenv
from .rekordbox.RekordboxDB import setup_db_connection
from .actions.AlbumSync import AlbumSync
from .actions.PlaylistSync import PlaylistSync
from .actions.TrackSync import TrackSync
from .utils.helpers import determine_sync_targets, parse_script_arguments
from .utils.logger import init_logger

dotenv.load_dotenv()


def main():
    setup_db_connection()
    args = parse_script_arguments()
    init_logger(args)
    sync = determine_sync_targets(args)
    if "tracks" in sync:
        TrackSync(args).sync()
    if "playlists" in sync:
        PlaylistSync(args).sync()
    if "albums" in sync:
        AlbumSync(args).sync()
