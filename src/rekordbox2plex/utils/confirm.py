from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text
import sys

console = Console()


def confirm_warning(message: str, title: str = "Warning") -> bool:
    """Displays a styled warning and prompts the user for confirmation.

    Args:
        message (str): The warning message to display.
        title (str): Optional title for the warning panel.

    Returns:
        bool: True if the user confirms with 'y', False otherwise.
    """
    warning_text = Text(f"⚠ {message}", style="bold yellow")
    console.print(Panel(warning_text, title=title, border_style="red"))

    try:
        response = Prompt.ask(
            "Do you want to continue?", choices=["y", "n"], default="n"
        )
        return response.lower() == "y"
    except KeyboardInterrupt:
        console.print("\n[bold red]Operation aborted by user (Ctrl+C).[/bold red]")
        sys.exit(1)
