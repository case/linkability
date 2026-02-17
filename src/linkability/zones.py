"""Zone loading, downloading, and parsing."""

from __future__ import annotations

import json
import subprocess
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


def download_brand_zones(
    output_path: str | Path = "Data-Zones/zones-brand.txt",
    zonedb_dir: str | Path | None = None,
) -> None:
    """Fetch the brand zones list from the local ZoneDB CLI."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if zonedb_dir is None:
        zonedb_dir = Path.home() / "git" / "domainr" / "zonedb"

    result = subprocess.run(
        [
            "zonedb",
            "--tlds",
            "--delegated",
            "--tags",
            "brand",
            "--json",
            "--dir",
            str(zonedb_dir),
        ],
        capture_output=True,
    )

    json_data = result.stdout or result.stderr
    if not json_data:
        print("Error: No output from zonedb command")
        return

    try:
        data = json.loads(json_data)
        filtered = data.get("zones", {}).get("filtered", [])
    except (json.JSONDecodeError, KeyError):
        print("Error: Invalid JSON format from zonedb command")
        return

    zones_content = "\n".join(sorted(filtered))
    output_path.write_text(zones_content, encoding="utf-8")
    print(f"Brand zones saved to {output_path} ({len(filtered)} zones)")
