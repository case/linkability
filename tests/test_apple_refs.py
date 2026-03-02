"""Tests for Apple release date references."""

import re

from linkability.checks.apple_refs import APPLE_RELEASE_DATES


def test_apple_release_dates_not_empty() -> None:
    assert len(APPLE_RELEASE_DATES) > 0


def test_apple_release_dates_format() -> None:
    for version, date_str in APPLE_RELEASE_DATES.items():
        assert re.match(r"\d{4}-\d{2}-\d{2}$", date_str), (
            f"Bad date format for macOS {version}: {date_str}"
        )


def test_apple_release_dates_keys_are_major_versions() -> None:
    """Keys should be simple major version numbers (no dots)."""
    for key in APPLE_RELEASE_DATES:
        assert key.isdigit(), f"Expected major version number, got: {key}"
