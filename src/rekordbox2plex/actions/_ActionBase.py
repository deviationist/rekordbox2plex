from ..config import is_dry_run
from ..utils.logger import console
from rich.text import Text


class ActionBase:
    def __init__(self, action_name: str, quiet: bool = False):
        self.dry_run = is_dry_run()
        # `quiet` suppresses the banner so machine-readable output (e.g. the
        # parity command's --json) keeps stdout clean.
        if not quiet:
            console.print(
                Text(f"=== {action_name.upper()} ===", style="bold magenta underline")
            )
