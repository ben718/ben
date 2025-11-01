"""Utility helpers around ISO 8601 datetime handling."""
from __future__ import annotations

from datetime import datetime
from typing import Final

_ISO_Z_SUFFIX: Final[str] = "Z"


def _normalize_timezone(value: str) -> str:
    """Normalize timezone suffixes that Python struggles to parse.

    Python's :func:`datetime.fromisoformat` is quite strict about
    timezone suffixes.  In particular it cannot parse the common ``Z``
    suffix used to designate UTC nor offsets such as ``+0000`` where the
    colon separator is omitted.  This helper rewrites those forms into
    values that ``fromisoformat`` accepts.
    """

    if value.endswith(_ISO_Z_SUFFIX):
        # Replace trailing Z by the explicit UTC offset expected by
        # ``datetime.fromisoformat``.
        return value[:-1] + "+00:00"

    # Handle offsets such as +0000 or -0230 by inserting the missing
    # colon before the last two digits.  ``fromisoformat`` accepts
    # timezone offsets between -23:59 and +23:59 which all follow this
    # pattern when written without a colon.
    if len(value) >= 5:
        sign = value[-5]
        if sign in {"+", "-"}:
            tz_without_colon = value[-5:]
            if tz_without_colon[3] != ":":
                return value[:-5] + tz_without_colon[:3] + ":" + tz_without_colon[3:]

    return value


def parse_iso8601(value: str) -> datetime:
    """Parse an ISO 8601 timestamp into a :class:`datetime` object.

    The helper mirrors :func:`datetime.fromisoformat` but fixes a couple
    of incompatibilities with common ISO 8601 notations: the ``Z`` UTC
    suffix and offsets written without the colon separator (``+0000``).

    Args:
        value: The string to parse.

    Returns:
        The parsed :class:`datetime` instance.

    Raises:
        TypeError: If ``value`` is not a string.
        ValueError: If the string is empty or cannot be parsed.
    """

    if not isinstance(value, str):  # pragma: no cover - sanity check
        raise TypeError("parse_iso8601 expects a string input")

    text = value.strip()
    if not text:
        raise ValueError("ISO 8601 value cannot be empty")

    normalized = _normalize_timezone(text)

    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:  # pragma: no cover - rewrap for clarity
        raise ValueError(f"Invalid ISO 8601 datetime: {value!r}") from exc
