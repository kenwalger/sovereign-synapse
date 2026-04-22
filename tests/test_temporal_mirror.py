"""Tests for temporal_mirror range parsing and metadata time extraction."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from temporal_mirror import (
    _in_range,
    _metadata_datetime,
    _parse_timestamp_string,
    parse_inclusive_date_range,
)


def test_parse_range_year_span() -> None:
    r = parse_inclusive_date_range("2005-2010")
    assert r.start == datetime(2005, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert r.end.year == 2010 and r.end.month == 12


def test_parse_range_reversed_years() -> None:
    r = parse_inclusive_date_range("2010-2005")
    assert r.start.year == 2005
    assert r.end.year == 2010


def test_parse_range_single_year() -> None:
    r = parse_inclusive_date_range(" 2024 ")
    assert r.start.year == 2024 and r.end.year == 2024


def test_parse_range_invalid() -> None:
    with pytest.raises(ValueError):
        parse_inclusive_date_range("not-a-range")


def test_parse_timestamp_string() -> None:
    dt = _parse_timestamp_string("2025-06-06T11:27:59.564000")
    assert dt is not None
    assert dt.month == 6
    d2 = _parse_timestamp_string("2010-01-15 12:00:00")
    assert d2 is not None


def test_metadata_timestamp_and_year() -> None:
    d1 = _metadata_datetime(
        {
            "original_timestamp": "2008-03-01T00:00:00+00:00",
        },
    )
    assert d1 is not None and d1.year == 2008
    d2 = _metadata_datetime({"original_year": "2015"})
    assert d2 is not None and d2.year == 2015


def test_in_range() -> None:
    r = parse_inclusive_date_range("2005-2010")
    m = _metadata_datetime(
        {"original_timestamp": "2007-01-01T00:00:00Z"},
    )
    assert m is not None
    assert _in_range(m, r) is True
    m2 = _metadata_datetime(
        {"original_timestamp": "2011-01-01T00:00:00Z"},
    )
    assert _in_range(m2, r) is False
