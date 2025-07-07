from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
    TaskID
)

class NullProgress:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def add_task(self, *args, **kwargs):
        return 0

    def update(self, *args, **kwargs):
        pass

def progress_instance(enabled: bool = True) -> Progress | NullProgress:
    if enabled:
        return Progress(
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            TextColumn("{task.description}")
        )
    else:
        return NullProgress()

__all__ = ["Progress", "TaskID", "NullProgress", "progress_instance"]
