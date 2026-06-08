from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text
import sys

console = Console()


def confirm_destructive(
    message: str, token: str, title: str = "Destructive action"
) -> bool:
    """Prompt the user to type a literal token to confirm a destructive action.

    Returns True only when the user types `token` exactly (case-sensitive).
    Empty input or any other value aborts. Ctrl+C exits the process.
    """
    warning_text = Text(
        f"⚠ {message}\n\nType {token!r} (case-sensitive) to confirm.",
        style="bold yellow",
    )
    console.print(Panel(warning_text, title=title, border_style="red"))

    try:
        response = Prompt.ask(f"Type {token!r} to proceed", default="")
        return response == token
    except KeyboardInterrupt:
        console.print("\n[bold red]Operation aborted by user (Ctrl+C).[/bold red]")
        sys.exit(1)
