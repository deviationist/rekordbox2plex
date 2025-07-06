import logging
from rich.logging import RichHandler

logger = logging.getLogger("rekordbox2plex")

def init_logger(args):
    # Set logging level based on verbosity
    if args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
        handlers=[RichHandler(markup=True)]
    )

