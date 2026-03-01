"""Report generation: CSV and text summary output."""

from __future__ import annotations

from pathlib import Path

from .analyze import ZoneSummary, compute_summary
from .classify import classify_zone
from .zones import read_zones


def build_csv_rows(
    zones: list[str],
    brand_zones: set[str],
    check_results: dict[str, bool],
) -> list[list[str]]:
    """Build CSV rows from zone data and check results.

    Returns a list of rows (each a list of strings), starting with the header.
    """
    rows: list[list[str]] = [["Zone", "Type", "Is a Brand?", "Is linked?", "NIC URL"]]
    for zone in zones:
        zone_type, is_brand = classify_zone(zone, brand_zones)
        is_linked = check_results.get(zone, False)
        linked_symbol = "\u2705" if is_linked else "\u274c"
        nic_url = f"nic.{zone}"
        rows.append([zone, zone_type, str(is_brand).lower(), linked_symbol, nic_url])
    return rows


def generate_csv_report(
    platform: str,
    check_results: dict[str, bool],
    zones_path: str = "Data-Zones/zones-full.txt",
    brand_zones_path: str = "Data-Zones/zones-brand.txt",
    output_dir: str = "Reports",
) -> None:
    """Generate a CSV report for the given platform's check results."""
    zones = read_zones(zones_path)
    if not zones:
        print(f"No zones found in {zones_path}")
        return

    brand_zones = set(read_zones(brand_zones_path))
    rows = build_csv_rows(zones, brand_zones, check_results)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    report_file = out_path / f"Report-{platform}.csv"
    lines = [",".join(row) for row in rows]
    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"CSV saved to {report_file}")


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
