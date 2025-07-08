from ..config import is_dry_run
from ..utils.logger import console
from rich.text import Text


class ActionBase:
    def __init__(self, action_name: str):
        self.dry_run = is_dry_run()
        console.print(
            Text(f"=== {action_name.upper()} ===", style="bold magenta underline")
        )
