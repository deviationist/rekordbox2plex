import sys
import dotenv
from . import config
from .rekordbox.RekordboxDB import setup_db_connection
from .actions.PlaylistSync import PlaylistSync
from .actions.PlaylistWipe import PlaylistWipe
from .actions.DateAddedRestore import DateAddedRestore
from .actions.ParityCheck import ParityCheck
from .actions.AiffTitleFix import AiffTitleFix
from .actions.LosslessTagCopy import LosslessTagCopy
from .actions.ArtistImageSync import ArtistImageSync
from .actions.ArtworkClear import ArtworkClear
from .utils.confirm import confirm_destructive
from .utils.helpers import parse_script_arguments
from .utils.logger import init_logger, logger
from .utils.paths import PROJECT_ROOT

dotenv.load_dotenv(PROJECT_ROOT / ".env")

WIPE_TOKEN = "WIPE"


def main():
    args = parse_script_arguments()
    config.set_args(args)
    init_logger(args)
    setup_db_connection()

    if config.get_command() == "dates":
        DateAddedRestore().run()
        logger.info("[bold green]✔ Date-added sync finished!")
        return

    if config.get_command() == "parity":
        ParityCheck().run()
        logger.info("[bold green]✔ Parity check finished!")
        return

    if config.get_command() == "aiff-titles":
        AiffTitleFix().run()
        logger.info("[bold green]✔ AIFF title fix finished!")
        return

    if config.get_command() == "lossless-tags":
        LosslessTagCopy().run()
        logger.info("[bold green]✔ Lossless tag copy finished!")
        return

    if config.get_command() == "artist-images":
        ArtistImageSync().run()
        logger.info("[bold green]✔ Artist image sync finished!")
        return

    if config.get_command() == "clear-art":
        ArtworkClear().run()
        logger.info("[bold green]✔ Clear artwork finished!")
        return

    # command == "playlists"
    if config.is_dry_run():
        logger.info("[cyan]This is a dry run! No changes will be made!")

    if config.should_wipe():
        if not config.is_dry_run() and not confirm_destructive(
            "This will delete ALL playlists in your Plex library.",
            WIPE_TOKEN,
        ):
            logger.info("[yellow]Wipe aborted — confirmation token did not match.")
            sys.exit(1)
        PlaylistWipe().wipe()
        logger.info("[bold green]✔ Wipe completed!")
    else:
        PlaylistSync().sync()
        logger.info("[bold green]✔ Sync completed!")
