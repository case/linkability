"""Tests for validation checks."""

from linkability.validate import find_cctld_brands, find_missing_brands, show_missing_brands
from linkability.zones import read_zones


# --- find_missing_brands (pure data) ---


def test_find_missing_brands_none_missing(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """All test brand zones are present in the full zone list."""
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))
    missing = find_missing_brands(zones, brand_zones)
    assert missing == set()


def test_find_missing_brands_some_missing() -> None:
    """Detects brand zones not in the zone list."""
    zones = ["com", "org", "uk"]
    brand_zones = {"com", "google", "nike"}
    missing = find_missing_brands(zones, brand_zones)
    assert missing == {"google", "nike"}


def test_find_missing_brands_returns_set() -> None:
    """Return type is a set."""
    missing = find_missing_brands(["com"], {"com"})
    assert isinstance(missing, set)


# --- find_cctld_brands (pure data) ---


def test_find_cctld_brands_none(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """No ccTLDs should be marked as brands in the test data."""
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))
    cctld_brands = find_cctld_brands(zones, brand_zones)
    assert cctld_brands == set()


def test_find_cctld_brands_detects_error() -> None:
    """Detects when a ccTLD is incorrectly in the brand set."""
    zones = ["com", "uk", "de", "google"]
    brand_zones = {"google", "uk"}  # uk is a ccTLD, shouldn't be a brand
    cctld_brands = find_cctld_brands(zones, brand_zones)
    assert cctld_brands == {"uk"}


def test_find_cctld_brands_ignores_non_cctld_brands() -> None:
    """gTLD brands are not flagged."""
    zones = ["com", "uk", "google", "nike"]
    brand_zones = {"google", "nike"}
    cctld_brands = find_cctld_brands(zones, brand_zones)
    assert cctld_brands == set()


# --- show_missing_brands (I/O wrapper, backward compat) ---


def test_show_missing_brands_output(
    test_zones_full_path: str,
    test_zones_brand_path: str,
    capsys,
) -> None:
    show_missing_brands(test_zones_full_path, test_zones_brand_path)
    captured = capsys.readouterr()
    assert "Delegated brands missing from root zone: 0" in captured.out
