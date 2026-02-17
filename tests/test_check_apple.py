"""Tests for Apple check (integration, macOS only)."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="Apple check requires macOS")


def test_apple_check_is_available() -> None:
    from linkability.checks.apple import AppleCheck

    check = AppleCheck()
    assert check.is_available() is True
    assert check.platform_name == "Apple"
