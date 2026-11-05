"""Tests for Apple release date references."""

import re
from pathlib import Path

import yaml

from linkability.checks.apple_refs import APPLE_RELEASE_DATES


def test_apple_release_dates_format() -> None:
    for version, date_str in APPLE_RELEASE_DATES.items():
        assert re.match(r"\d{4}-\d{2}-\d{2}$", date_str), (
            f"Bad date format for macOS {version}: {date_str}"
        )


def test_apple_release_dates_keys_are_major_versions() -> None:
    """Keys should be simple major version numbers (no dots)."""
    for key in APPLE_RELEASE_DATES:
        assert key.isdigit(), f"Expected major version number, got: {key}"


def test_every_apple_runner_has_a_release_date() -> None:
    """Each runner label in the Apple matrix names a macOS major that has a release date."""
    workflow = Path(__file__).parent.parent / ".github" / "workflows" / "apple-check.yml"
    labels = yaml.safe_load(workflow.read_text())["jobs"]["check"]["strategy"]["matrix"]["os"]
    assert labels, "no runner labels parsed; the guard is vacuous"
    for label in labels:
        match = re.fullmatch(r"(?:macos|xcode)-(\d+)", label)
        assert match, f"Unrecognized Apple runner label: {label}"
        assert match.group(1) in APPLE_RELEASE_DATES, f"Missing release date for {label}"
