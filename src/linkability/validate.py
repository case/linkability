"""Validation checks: missing brands, ccTLD-brand consistency."""

from __future__ import annotations

from pathlib import Path

from .zones import read_zones


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
    root_zones = set(zones)

    missing_brands = brand_zones - root_zones

    print()
    print("Delegated brand zones missing from root zone file:")
    print(f"Total delegated brand zones: {len(brand_zones)}")
    print(f"Delegated brands in root zone: {len(brand_zones & root_zones)}")
    print(f"Delegated brands missing from root zone: {len(missing_brands)}")
    print()

    if missing_brands:
        print("Missing delegated brand zones:")
        for brand in sorted(missing_brands):
            print(f"  {brand}")
    else:
        print("All delegated brand zones are present in the root zone file!")


def test_cctld_brands(report_path: str = "Reports/Report-Apple.csv") -> None:
    """Verify no ccTLDs are marked as brands in the CSV report."""
    print("Testing: Verifying no ccTLDs are marked as brands...")

    path = Path(report_path)
    if not path.exists():
        print(f"Error: Could not read {report_path}")
        return

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    cctld_brand_count = 0
    cctld_brand_examples: list[str] = []

    for i, line in enumerate(lines):
        if i == 0 or not line:
            continue
        columns = line.split(",")
        if len(columns) < 4:
            continue

        zone = columns[0]
        zone_type = columns[1]
        is_brand = columns[2]

        if zone_type == "ccTLD" and is_brand == "true":
            cctld_brand_count += 1
            if len(cctld_brand_examples) < 5:
                cctld_brand_examples.append(zone)

    if cctld_brand_count == 0:
        print("PASS: No ccTLDs are marked as brands")
    else:
        print(f"FAIL: Found {cctld_brand_count} ccTLD(s) marked as brands:")
        for example in cctld_brand_examples:
            print(f"  - {example}")
        if cctld_brand_count > len(cctld_brand_examples):
            print(f"  ... and {cctld_brand_count - len(cctld_brand_examples)} more")
