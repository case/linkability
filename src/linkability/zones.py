"""Zone loading, downloading, and parsing."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path


def read_zones(filepath: str | Path) -> list[str]:
    """Parse a zone file, stripping comments/blanks, lowercasing, and decoding Punycode."""
    import idna

    path = Path(filepath)
    if not path.exists():
        print(f"Error reading file: {filepath}")
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    zones: list[str] = []
    for line in lines:
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        lowered = trimmed.lower()
        if lowered.startswith("xn--"):
            try:
                decoded = idna.decode(lowered)
                zones.append(decoded)
            except (idna.core.IDNAError, UnicodeError):
                zones.append(lowered)
        else:
            zones.append(lowered)
    return zones


def download_iana_zones(output_path: str | Path = "Data-Zones/zones-full.txt") -> None:
    """Download the IANA TLD list, skipping write if only the timestamp changed."""
    url = "https://data.iana.org/TLD/tlds-alpha-by-domain.txt"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(url) as response:
        new_content = response.read().decode("utf-8")

    # Extract zone data after the first line (skip version/timestamp)
    new_lines = new_content.splitlines()
    new_zone_data = "\n".join(new_lines[1:])

    if output_path.exists():
        existing_content = output_path.read_text(encoding="utf-8")
        existing_lines = existing_content.splitlines()
        existing_zone_data = "\n".join(existing_lines[1:])
        if new_zone_data == existing_zone_data:
            print("Zone data unchanged (only timestamp updated). Skipping file write.")
            return

    output_path.write_text(new_content, encoding="utf-8")
    print(f"Zones updated and saved to {output_path}")


_TLDS_JSON_URL = (
    "https://raw.githubusercontent.com/case/iana-data"
    "/refs/heads/main/data/generated/tlds.json"
)


def download_brand_zones(
    output_path: str | Path = "Data-Zones/zones-brand.txt",
    cache_path: str | Path = "Data-Zones/tlds.json",
) -> None:
    """Fetch brand zones from case/iana-data tlds.json.

    Downloads tlds.json (caching locally), extracts TLDs with "brand" in
    annotations.registry_agreement_types, and writes the sorted list to output_path.
    """
    cache_path = Path(cache_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not cache_path.exists():
        print("Downloading tlds.json...")
        with urllib.request.urlopen(_TLDS_JSON_URL) as response:
            cache_path.write_bytes(response.read())
        print(f"Cached to {cache_path}")
    else:
        print(f"Using cached {cache_path}")

    brands = extract_brand_zones(cache_path)

    zones_content = "\n".join(sorted(brands))
    output_path.write_text(zones_content, encoding="utf-8")
    print(f"Brand zones saved to {output_path} ({len(brands)} zones)")


def load_zone_data(
    zones_path: str | Path,
    brand_zones_path: str | Path,
) -> tuple[list[str], set[str]]:
    """Load zones and brand zones from their respective files.

    Returns (zones, brand_zones) where zones is a list of all TLDs
    and brand_zones is a set of brand TLD names.
    """
    zones = read_zones(zones_path)
    brand_zones = set(read_zones(brand_zones_path))
    return zones, brand_zones


def extract_brand_zones(tlds_json_path: str | Path) -> set[str]:
    """Extract brand zone names from a tlds.json file.

    Brand TLDs are identified by "brand" in annotations.registry_agreement_types.
    Returns lowercased zone names.
    """
    path = Path(tlds_json_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    brands: set[str] = set()
    for entry in data["tlds"]:
        agreement_types = entry.get("annotations", {}).get(
            "registry_agreement_types", []
        )
        if "brand" in agreement_types:
            brands.add(entry["tld"].lower())

    return brands
