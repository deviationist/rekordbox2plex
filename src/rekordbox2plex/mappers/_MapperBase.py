from typing import Any


class MapperBase:
    def __init__(self) -> None:
        self.did_change = False
        self.edits: dict[str, Any] = {}

    def add_change(self, field: str, value: Any):
        self.did_change = True
        self.edits[field] = value
