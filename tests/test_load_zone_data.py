"""Tests for load_zone_data() — centralized zone loading."""

from linkability.zones import load_zone_data


def test_load_zone_data_returns_zones_and_brands(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """Returns a (zones, brand_zones) tuple."""
    zones, brand_zones = load_zone_data(test_zones_full_path, test_zones_brand_path)
    assert isinstance(zones, list)
    assert isinstance(brand_zones, set)


def test_load_zone_data_zones_content(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """Zones list matches expected test data."""
    zones, _ = load_zone_data(test_zones_full_path, test_zones_brand_path)
    assert len(zones) == 14
    assert "com" in zones
    assert "uk" in zones
    assert "vermögensberater" in zones


def test_load_zone_data_brand_content(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """Brand zones set matches expected test data."""
    _, brand_zones = load_zone_data(test_zones_full_path, test_zones_brand_path)
    assert brand_zones == {"audi", "bmw", "google", "microsoft", "nike"}


def test_load_zone_data_brands_subset_of_zones(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """Brand zones should be a subset of all zones."""
    zones, brand_zones = load_zone_data(test_zones_full_path, test_zones_brand_path)
    assert brand_zones <= set(zones)
