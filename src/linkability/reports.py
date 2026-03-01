"""Report generation: snapshot CSVs, manifest, summary, and text output."""

from __future__ import annotations

import json
from pathlib import Path

from .analyze import ZoneSummary, compute_summary
from .classify import classify_zone, is_cctld
from .zones import read_zones


# --- Snapshot CSV ---


def build_csv_rows(
    zones: list[str],
    brand_zones: set[str],
    check_results: dict[str, bool],
) -> list[list[str]]:
    """Build CSV rows from zone data and check results.

    Returns a list of rows (each a list of strings), starting with the header.
    Format: Zone,Type,Brand,Linked with true/false booleans.
    """
    type_labels = {"cc": "cctld", "g": "gtld"}
    rows: list[list[str]] = [["Zone", "Type", "Brand", "AutoLinked"]]
    for zone in zones:
        zone_type, is_brand = classify_zone(zone, brand_zones)
        is_linked = check_results.get(zone, False)
        rows.append([zone, type_labels[zone_type], str(is_brand).lower(), str(is_linked).lower()])
    return rows


def write_snapshot(
    platform: str,
    version: str,
    rows: list[list[str]],
    output_dir: str = "Reports",
) -> Path:
    """Write snapshot CSV to {output_dir}/snapshots/{platform}/{version}.csv."""
    snapshot_dir = Path(output_dir) / "snapshots" / platform
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{version}.csv"
    lines = [",".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --- Manifest ---


def build_manifest_entry(
    platform: str,
    platform_type: str,
    version: str,
    check_date: str,
    file_rel: str,
    zones: list[str],
    brand_zones: set[str],
    check_results: dict[str, bool],
) -> dict:
    """Build a manifest entry dict with zone counts and linked counts."""
    cctld_count = 0
    gtld_count = 0
    brand_count = 0
    linked_total = 0
    linked_cctlds = 0
    linked_gtlds = 0
    linked_brands = 0

    for zone in zones:
        is_linked = check_results.get(zone, False)
        if is_linked:
            linked_total += 1

        if is_cctld(zone):
            cctld_count += 1
            if is_linked:
                linked_cctlds += 1
        else:
            gtld_count += 1
            if is_linked:
                linked_gtlds += 1
            if zone in brand_zones:
                brand_count += 1
                if is_linked:
                    linked_brands += 1

    return {
        "platform": platform,
        "platform_type": platform_type,
        "platform_version": version,
        "check_date": check_date,
        "file": file_rel,
        "zones_count": len(zones),
        "cctld_count": cctld_count,
        "gtld_count": gtld_count,
        "brand_count": brand_count,
        "linked_total": linked_total,
        "linked_cctlds": linked_cctlds,
        "linked_gtlds": linked_gtlds,
        "linked_brands": linked_brands,
    }


def load_manifest(output_dir: str = "Reports") -> list[dict]:
    """Load manifest entries from manifest.json, or empty list if missing."""
    path = Path(output_dir) / "manifest.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("snapshots", [])


def save_manifest(entries: list[dict], output_dir: str = "Reports") -> None:
    """Write manifest.json with the given entries."""
    path = Path(output_dir) / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"snapshots": entries}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def upsert_manifest_entry(
    entries: list[dict], new_entry: dict
) -> list[dict]:
    """Add or replace a manifest entry, keyed by platform + platform_version."""
    key = (new_entry["platform"], new_entry["platform_version"])
    result = [
        e for e in entries
        if (e["platform"], e["platform_version"]) != key
    ]
    result.append(new_entry)
    return result


# --- Summary CSV ---


_SUMMARY_HEADER = [
    "platform", "platform_type", "platform_version", "check_date",
    "zones_count", "cctld_count", "gtld_count", "brand_count",
    "linked_total", "linked_cctlds", "linked_gtlds", "linked_brands",
    "linked_pct",
]


def build_summary_csv(entries: list[dict]) -> list[list[str]]:
    """Build summary CSV rows from manifest entries."""
    rows: list[list[str]] = [list(_SUMMARY_HEADER)]
    for entry in entries:
        zones_count = entry.get("zones_count", 0)
        linked_total = entry.get("linked_total", 0)
        linked_pct = (
            round(linked_total / zones_count * 100, 1) if zones_count > 0 else 0.0
        )
        rows.append([
            entry.get("platform", ""),
            entry.get("platform_type", ""),
            entry.get("platform_version", ""),
            entry.get("check_date", ""),
            str(zones_count),
            str(entry.get("cctld_count", 0)),
            str(entry.get("gtld_count", 0)),
            str(entry.get("brand_count", 0)),
            str(linked_total),
            str(entry.get("linked_cctlds", 0)),
            str(entry.get("linked_gtlds", 0)),
            str(entry.get("linked_brands", 0)),
            str(linked_pct),
        ])
    return rows


def save_summary_csv(entries: list[dict], output_dir: str = "Reports") -> None:
    """Write summary.csv from manifest entries."""
    rows = build_summary_csv(entries)
    path = Path(output_dir) / "summary.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- Text summary (unchanged from Phase 0) ---


def format_summary(summary: ZoneSummary, platform: str) -> str:
    """Format a ZoneSummary as a human-readable string."""

    def fmt(n: int) -> str:
        return f"{n:,}"

    lines = [
        "",
        f"** {platform} platforms stdlib + auto-linking summary **",
        "",
        "Summary of all zones:",
        f"- {fmt(summary.total_zones)}\t Total IANA zones",
        f"- {fmt(summary.gtld_count)}\t gTLDs, {summary.gtld_percentage_of_total:.1f}% of total",
        f"- {fmt(summary.gtld_brand_count)}\t - Brand gTLDs, "
        f"{summary.gtld_brand_percentage_of_gtld:.1f}% of gTLDs and "
        f"{summary.gtld_brand_percentage_of_total:.1f}% of all zones",
        f"- {fmt(summary.cctld_count)}\t ccTLDs, {summary.cctld_percentage_of_total:.1f}% of total",
        "",
        "Auto-linked zones:",
        f"- {fmt(summary.total_linked_zones)}\t {summary.total_linked_percentage:.1f}% of all zones total",
        f"- {fmt(summary.cctld_linked)}\t {summary.cctld_linkable_percentage:.1f}% of ccTLDs and "
        f"{summary.cctld_linked_percentage_of_total:.1f}% of all zones",
        f"- {fmt(summary.gtld_linked)}\t {summary.gtld_linkable_percentage:.1f}% of gTLDs and "
        f"{summary.gtld_linked_percentage_of_total:.1f}% of all zones",
        f"- {fmt(summary.gtld_non_brand_linked)}\t {summary.gtld_non_brand_linkable_percentage:.1f}% of non-brand gTLDs and "
        f"{summary.gtld_non_brand_linked_percentage_of_total:.1f}% of all zones",
        f"- {fmt(summary.gtld_brand_linked)}\t {summary.gtld_brand_linkable_percentage:.1f}% of brand gTLDs and "
        f"{summary.gtld_brand_linked_percentage_of_total:.1f}% of all zones",
    ]
    return "\n".join(lines)


def generate_summary(
    platform: str,
    check_results: dict[str, bool],
    *,
    zones: list[str] | None = None,
    brand_zones: set[str] | None = None,
    zones_path: str = "Data-Zones/zones-full.txt",
    brand_zones_path: str = "Data-Zones/zones-brand.txt",
) -> None:
    """Print a human-readable summary for the given platform.

    Accepts zone data directly via zones/brand_zones, or falls back to
    loading from zones_path/brand_zones_path.
    """
    if zones is None:
        zones = read_zones(zones_path)
        if not zones:
            print(f"No zones found in {zones_path}")
            return

    if brand_zones is None:
        brand_zones = set(read_zones(brand_zones_path))

    summary = compute_summary(zones, brand_zones, check_results)
    print(format_summary(summary, platform))
