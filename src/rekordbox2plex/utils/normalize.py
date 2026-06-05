import re

_WS = re.compile(r"\s+")


def normalize(value: str | None) -> str:
    """Normalize a metadata value for *comparison only* (not display).

    Folds away the trivial tag-formatting differences that otherwise drown a
    parity check in noise: surrounding whitespace, repeated internal whitespace,
    and letter case. ``None`` collapses to the empty string so a missing value on
    one side compares equal to an empty value on the other.

    The report always shows the *raw* values; this is used purely to decide
    whether two values are considered equal.
    """
    if value is None:
        return ""
    return _WS.sub(" ", value.strip()).casefold()
