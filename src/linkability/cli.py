"""CLI entry point — argparse-based command dispatcher."""

from __future__ import annotations

import argparse
import sys

from .checks.android import AndroidCheck
from .checks.apple import AppleCheck
from .checks.electron import ElectronCheck
from .checks.windows import WindowsCheck
from .classify import is_cctld
from .reports import generate_csv_report, generate_summary
from .validate import find_cctld_brands, show_missing_brands
from .zones import download_brand_zones, download_iana_zones, load_zone_data

_CHECKS = {
    "apple": AppleCheck,
    "android": AndroidCheck,
    "electron": ElectronCheck,
    "windows": WindowsCheck,
}


def _get_check(platform: str):
    cls = _CHECKS.get(platform)
    if cls is None:
        print(f"Unknown platform: {platform}. Available: {', '.join(_CHECKS)}")
        sys.exit(1)
    check = cls()
    if not check.is_available():
        print(f"Platform check '{platform}' is not available on this system.")
        sys.exit(1)
    return check


_ZONES_PATH = "Data-Zones/zones-full.txt"
_BRAND_ZONES_PATH = "Data-Zones/zones-brand.txt"


def _load_zones() -> tuple[list[str], set[str]]:
    """Load zone data, exiting on failure."""
    zones, brand_zones = load_zone_data(_ZONES_PATH, _BRAND_ZONES_PATH)
    if not zones:
        print(f"No zones found in {_ZONES_PATH}")
        sys.exit(1)
    return zones, brand_zones


def _run_check(platform: str, zones: list[str]) -> dict[str, bool]:
    """Run a platform check and return results."""
    check = _get_check(platform)
    return check.check_zones(zones)


def cmd_download_zones(args: argparse.Namespace) -> None:
    download_iana_zones()


def cmd_download_brands(args: argparse.Namespace) -> None:
    download_brand_zones()


def cmd_report_csv(args: argparse.Namespace) -> None:
    zones, brand_zones = _load_zones()
    results = _run_check(args.platform, zones)
    generate_csv_report(
        args.platform.capitalize(), results,
        zones_path=_ZONES_PATH, brand_zones_path=_BRAND_ZONES_PATH,
    )


def cmd_report_summary(args: argparse.Namespace) -> None:
    zones, brand_zones = _load_zones()
    results = _run_check(args.platform, zones)
    generate_summary(
        args.platform.capitalize(), results,
        zones=zones, brand_zones=brand_zones,
    )


def cmd_list_linked(args: argparse.Namespace) -> None:
    zones, brand_zones = _load_zones()
    results = _run_check(args.platform, zones)

    linked: list[str] = []
    for zone in zones:
        if not results.get(zone, False):
            continue

        is_cc = is_cctld(zone)
        is_brand = zone in brand_zones

        if args.type == "cctld" and is_cc:
            linked.append(zone)
        elif args.type == "gtld" and not is_cc:
            linked.append(zone)
        elif args.type == "brand" and not is_cc and is_brand:
            linked.append(zone)

    sorted_linked = sorted(linked)
    type_desc = {"cctld": "ccTLD", "gtld": "gTLD", "brand": "brand gTLD"}[args.type]
    print(f"\nLinked {type_desc} zones ({len(sorted_linked)}):")
    if sorted_linked:
        print(" ".join(sorted_linked))
    else:
        print(f"No linked {type_desc} zones found")


def cmd_validate_missing_brands(args: argparse.Namespace) -> None:
    show_missing_brands(_ZONES_PATH, _BRAND_ZONES_PATH)


def cmd_validate_cctld_brands(args: argparse.Namespace) -> None:
    zones, brand_zones = _load_zones()
    cctld_brands = find_cctld_brands(zones, brand_zones)
    if not cctld_brands:
        print("PASS: No ccTLDs are marked as brands")
    else:
        print(f"FAIL: Found {len(cctld_brands)} ccTLD(s) marked as brands:")
        for zone in sorted(cctld_brands):
            print(f"  - {zone}")


def cmd_check(args: argparse.Namespace) -> None:
    zones, _ = _load_zones()
    results = _run_check(args.platform, zones)
    linked = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n{args.platform.capitalize()} check: {linked}/{total} zones linked")


class _HelpFormatter(argparse.HelpFormatter):
    """Capitalizes section headings and the usage prefix."""

    def start_section(self, heading: str | None) -> None:
        if heading:
            heading = heading[0].upper() + heading[1:]
        super().start_section(heading)

    def _format_usage(self, usage, actions, groups, prefix):
        if prefix is None:
            prefix = "Usage: "
        return super()._format_usage(usage, actions, groups, prefix)


class _ArgumentParser(argparse.ArgumentParser):
    """ArgumentParser with capitalized output and improved error formatting."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _HelpFormatter)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"\nError: {message}\n")


def main() -> None:
    parser = _ArgumentParser(
        prog="linkability",
        description="Measures how well tech platforms auto-link IANA top-level domains.",
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, title="commands", metavar=""
    )

    # download
    dl = subparsers.add_parser("download", help="Download zone data")
    dl_sub = dl.add_subparsers(dest="target", required=True)
    dl_zones = dl_sub.add_parser("zones", help="Download latest TLD zones from IANA")
    dl_zones.set_defaults(func=cmd_download_zones)
    dl_brands = dl_sub.add_parser("brands", help="Fetch brand zones from local ZoneDB CLI")
    dl_brands.set_defaults(func=cmd_download_brands)

    # report
    rpt = subparsers.add_parser("report", help="Generate reports")
    rpt_sub = rpt.add_subparsers(dest="format", required=True)
    rpt_csv = rpt_sub.add_parser("csv", help="Generate CSV report")
    rpt_csv.add_argument("--platform", required=True, choices=list(_CHECKS))
    rpt_csv.set_defaults(func=cmd_report_csv)
    rpt_summary = rpt_sub.add_parser("summary", help="Print text summary")
    rpt_summary.add_argument("--platform", required=True, choices=list(_CHECKS))
    rpt_summary.set_defaults(func=cmd_report_summary)

    # list
    lst = subparsers.add_parser("list", help="List linked zones")
    lst_sub = lst.add_subparsers(dest="action", required=True)
    lst_linked = lst_sub.add_parser("linked", help="Show linked zones by type")
    lst_linked.add_argument("--type", required=True, choices=["cctld", "gtld", "brand"])
    lst_linked.add_argument("--platform", required=True, choices=list(_CHECKS))
    lst_linked.set_defaults(func=cmd_list_linked)

    # validate
    val = subparsers.add_parser("validate", help="Run validation checks")
    val_sub = val.add_subparsers(dest="check", required=True)
    val_missing = val_sub.add_parser("missing-brands", help="Show missing brand zones")
    val_missing.set_defaults(func=cmd_validate_missing_brands)
    val_cctld = val_sub.add_parser("cctld-brands", help="Test no ccTLDs are marked as brands")
    val_cctld.set_defaults(func=cmd_validate_cctld_brands)

    # check
    chk = subparsers.add_parser("check", help="Run a platform check")
    chk.add_argument("platform", choices=list(_CHECKS))
    chk.set_defaults(func=cmd_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
