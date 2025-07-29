import dotenv
from . import config
from .rekordbox.RekordboxDB import setup_db_connection
from .actions.TrackSync import TrackSync
from .actions.PlaylistSync import PlaylistSync
from .actions.AlbumSync import AlbumSync
from .actions.TrackWipe import TrackWipe
from .actions.PlaylistWipe import PlaylistWipe
from .actions.AlbumWipe import AlbumWipe
from .utils.helpers import (
    determine_targets,
    parse_script_arguments,
    check_for_dangerous_config,
)
from .utils.logger import init_logger, logger, console

dotenv.load_dotenv()


def main():
    args = parse_script_arguments()
    config.set_args(args)
    init_logger(args)
    setup_db_connection()
    targets, affect_all = determine_targets(args)
    sync_target_count = len(targets)

    if config.is_dry_run():
        logger.info("[cyan]This is a dry run! No changes will be made!")
    else:
        check_for_dangerous_config()

    for i, item in enumerate(targets):
        if item == "tracks":
            if config.should_wipe():
                TrackWipe().wipe()
            else:
                TrackSync().sync()
        if item == "playlists":
            if config.should_wipe():
                PlaylistWipe().wipe()
            else:
                PlaylistSync().sync()
        if item == "albums":
            if config.should_wipe():
                AlbumWipe().wipe()
            else:
                AlbumSync().sync()
        if sync_target_count > 1 and i != sync_target_count - 1:
            console.rule()

    if affect_all:
        if config.should_wipe():
            logger.info("[bold green]✔ Full wipe completed!")
        else:
            logger.info("[bold green]✔ Full sync completed!")
