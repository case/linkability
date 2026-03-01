"""Validation checks: missing brands, ccTLD-brand consistency."""

from __future__ import annotations

from .classify import is_cctld
from .zones import read_zones


def find_missing_brands(zones: list[str], brand_zones: set[str]) -> set[str]:
    """Return brand zones that are not in the zone list."""
    return brand_zones - set(zones)


def find_cctld_brands(zones: list[str], brand_zones: set[str]) -> set[str]:
    """Return any ccTLDs that are incorrectly in the brand set."""
    return {zone for zone in zones if is_cctld(zone) and zone in brand_zones}


def show_missing_brands(
    zones_path: str = "Data-Zones/zones-full.txt",
    brand_zones_path: str = "Data-Zones/zones-brand.txt",
) -> None:
    """Show delegated brand zones not in the root zone file."""
    print("Checking for delegated brand zones not in root zone file...")

    zones = read_zones(zones_path)
    if not zones:
        print(f"Error: No zones found in {zones_path}")
        return

    brand_zones = set(read_zones(brand_zones_path))
    missing = find_missing_brands(zones, brand_zones)

    print()
    print("Delegated brand zones missing from root zone file:")
    print(f"Total delegated brand zones: {len(brand_zones)}")
    print(f"Delegated brands in root zone: {len(brand_zones - missing)}")
    print(f"Delegated brands missing from root zone: {len(missing)}")
    print()

    if missing:
        print("Missing delegated brand zones:")
        for brand in sorted(missing):
            print(f"  {brand}")
    else:
        print("All delegated brand zones are present in the root zone file!")
