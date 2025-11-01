from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from datetime_utils import parse_iso8601


def test_parse_supports_z_suffix():
    result = parse_iso8601("2024-03-04T10:30:00Z")
    assert result == datetime(2024, 3, 4, 10, 30, tzinfo=timezone.utc)


def test_parse_supports_timezone_without_colon():
    result = parse_iso8601("1999-12-31T23:59:59+0000")
    assert result == datetime(1999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)


def test_parse_preserves_custom_offset():
    result = parse_iso8601("2001-09-09T01:46:40-0530")
    expected_offset = timezone(-timedelta(hours=5, minutes=30))
    assert result == datetime(2001, 9, 9, 1, 46, 40, tzinfo=expected_offset)


def test_parse_rejects_invalid_values():
    with pytest.raises(ValueError):
        parse_iso8601("not-a-date")


@pytest.mark.parametrize("value", ["", "   "])
def test_parse_rejects_empty_values(value: str):
    with pytest.raises(ValueError):
        parse_iso8601(value)
