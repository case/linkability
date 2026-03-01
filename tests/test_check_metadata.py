"""Tests for platform check metadata — platform_type and platform_version."""

import sys

import pytest

from linkability.checks.base import Check


def test_check_abc_has_platform_type() -> None:
    """Check ABC declares platform_type as an abstract property."""
    assert hasattr(Check, "platform_type")


def test_check_abc_has_platform_version() -> None:
    """Check ABC declares platform_version as an abstract property."""
    assert hasattr(Check, "platform_version")


def test_stub_checks_have_metadata() -> None:
    """Stub checks (Electron, Windows) implement platform_type and platform_version."""
    from linkability.checks.electron import ElectronCheck
    from linkability.checks.windows import WindowsCheck

    electron = ElectronCheck()
    assert electron.platform_type == "framework"
    assert electron.platform_version == "unknown"

    windows = WindowsCheck()
    assert windows.platform_type == "os"
    assert windows.platform_version == "unknown"


def test_android_check_metadata() -> None:
    """AndroidCheck reports platform_type as 'os'."""
    from linkability.checks.android import AndroidCheck

    check = AndroidCheck()
    assert check.platform_type == "os"
    assert isinstance(check.platform_version, str)


@pytest.mark.skipif(sys.platform != "darwin", reason="Apple check requires macOS")
def test_apple_check_metadata() -> None:
    """AppleCheck reports platform_type as 'os' and detects macOS version."""
    from linkability.checks.apple import AppleCheck

    check = AppleCheck()
    assert check.platform_type == "os"
    version = check.platform_version
    assert isinstance(version, str)
    # macOS version should look like "X.Y" or "X.Y.Z"
    parts = version.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts)
