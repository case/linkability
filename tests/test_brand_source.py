"""Tests for brand zone extraction from case/iana-data tlds.json."""

from pathlib import Path

from linkability.zones import extract_brand_zones


def test_extract_brand_zones_returns_only_brands(test_data_dir: Path) -> None:
    """Only TLDs with "brand" in annotations.registry_agreement_types are returned."""
    brands = extract_brand_zones(test_data_dir / "test-tlds.json")
    assert brands == {"audi", "bmw", "google", "microsoft", "nike"}


def test_extract_brand_zones_excludes_non_brands(test_data_dir: Path) -> None:
    """Non-brand gTLDs and ccTLDs are excluded."""
    brands = extract_brand_zones(test_data_dir / "test-tlds.json")
    assert "com" not in brands
    assert "org" not in brands
    assert "uk" not in brands
    assert "test" not in brands


def test_extract_brand_zones_lowercases(test_data_dir: Path) -> None:
    """Zone names are lowercased."""
    brands = extract_brand_zones(test_data_dir / "test-tlds.json")
    for zone in brands:
        assert zone == zone.lower()


def test_extract_brand_zones_empty_annotations(test_data_dir: Path) -> None:
    """Entries with empty annotations or no registry_agreement_types are skipped."""
    brands = extract_brand_zones(test_data_dir / "test-tlds.json")
    # "test" has empty annotations, "de" has annotations but no registry_agreement_types
    assert "test" not in brands
    assert "de" not in brands


def test_extract_brand_zones_returns_set(test_data_dir: Path) -> None:
    """Return type is a set for efficient membership testing."""
    brands = extract_brand_zones(test_data_dir / "test-tlds.json")
    assert isinstance(brands, set)
