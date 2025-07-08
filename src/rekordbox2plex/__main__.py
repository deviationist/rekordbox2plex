import dotenv
from . import config
from .rekordbox.RekordboxDB import setup_db_connection
from .actions.TrackSync import TrackSync
from .actions.PlaylistSync import PlaylistSync
from .actions.AlbumSync import AlbumSync
from .utils.helpers import determine_sync_targets, parse_script_arguments
from .utils.logger import init_logger, logger, console

dotenv.load_dotenv()


def main():
    args = parse_script_arguments()
    config.set_args(args)
    init_logger(args)
    setup_db_connection()
    sync_targets = determine_sync_targets(args)
    sync_all = "all" in sync_targets

    if config.is_dry_run():
        logger.info("[cyan]This is a dry run! No changes will be made!")

    for i, sync_item in enumerate(sync_targets):
        if sync_all or sync_item == "tracks":
            TrackSync().sync()
        if sync_all or sync_item == "playlists":
            PlaylistSync().sync()
        if sync_all or sync_item == "albums":
            AlbumSync().sync()
        if i != len(sync_targets) - 1:
            console.rule()

    if sync_all:
        logger.info("[bold green]✔ Full sync completed!")
