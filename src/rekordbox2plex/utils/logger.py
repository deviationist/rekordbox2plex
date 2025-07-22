import logging
import argparse
from rich.logging import RichHandler
from rich.console import Console
from rich.rule import Rule
from ..config import get_logger_name

logger = logging.getLogger(get_logger_name())
console = Console()


def print_debug_hr():
    if logger.isEnabledFor(logging.DEBUG):
        console.print()
        console.print(Rule(style="dim"))


def init_logger(args: argparse.Namespace) -> None:
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
        handlers=[RichHandler(markup=True)],
    )
