"""Tests for zone loading and parsing."""

from linkability.zones import read_zones


def test_read_zones_from_test_data(test_zones_full_path: str) -> None:
    zones = read_zones(test_zones_full_path)

    # Should read 14 zones (excluding comments and empty lines)
    assert len(zones) == 14, f"Should read 14 zones from test data, got {len(zones)}"

    # Should contain expected zones
    assert "com" in zones
    assert "org" in zones
    assert "au" in zones  # ccTLD
    assert "uk" in zones  # ccTLD
    assert "audi" in zones  # brand
    assert "vermögensberater" in zones  # decoded Punycode
    assert "コム" in zones  # Japanese zone


def test_read_zones_strips_comments(test_zones_full_path: str) -> None:
    zones = read_zones(test_zones_full_path)
    for zone in zones:
        assert not zone.startswith("#"), "Should not contain comment lines"
        assert zone != "", "Should not contain empty strings"


def test_read_brand_zones(test_zones_brand_path: str) -> None:
    brand_zones = read_zones(test_zones_brand_path)

    assert len(brand_zones) == 5, f"Should read 5 brand zones, got {len(brand_zones)}"
    assert "audi" in brand_zones
    assert "bmw" in brand_zones
    assert "google" in brand_zones
    assert "microsoft" in brand_zones
    assert "nike" in brand_zones


def test_punycode_decoding(test_zones_full_path: str) -> None:
    zones = read_zones(test_zones_full_path)
    assert "vermögensberater" in zones, "Should decode xn--vermgensberater-ctb"
    assert "xn--vermgensberater-ctb" not in zones, "Should not contain original Punycode form"


def test_read_zones_nonexistent_file() -> None:
    zones = read_zones("/nonexistent/path/zones.txt")
    assert zones == []
