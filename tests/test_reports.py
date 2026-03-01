"""Tests for report generation."""

import tempfile
from pathlib import Path

from linkability.reports import build_csv_rows, format_summary, generate_csv_report, generate_summary
from linkability.analyze import ZoneSummary
from linkability.zones import read_zones


# --- build_csv_rows (pure computation, no I/O) ---


def test_build_csv_rows_returns_header_and_data(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """build_csv_rows returns a header row plus one row per zone."""
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))
    check_results = {"com": True, "org": True}

    rows = build_csv_rows(zones, brand_zones, check_results)
    assert rows[0] == ["Zone", "Type", "Is a Brand?", "Is linked?", "NIC URL"]
    assert len(rows) == len(zones) + 1  # header + one per zone


def test_build_csv_rows_linked_symbols(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """Linked zones get checkmark, unlinked get X."""
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))
    check_results = {"com": True, "uk": True}

    rows = build_csv_rows(zones, brand_zones, check_results)
    data_rows = {row[0]: row for row in rows[1:]}

    assert data_rows["com"][3] == "\u2705"
    assert data_rows["uk"][3] == "\u2705"
    assert data_rows["org"][3] == "\u274c"
    assert data_rows["audi"][3] == "\u274c"


def test_build_csv_rows_classification(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """Zones are correctly classified as ccTLD/gTLD and brand/non-brand."""
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))
    check_results = {}

    rows = build_csv_rows(zones, brand_zones, check_results)
    data_rows = {row[0]: row for row in rows[1:]}

    # ccTLD
    assert data_rows["uk"][1] == "cc"
    assert data_rows["uk"][2] == "false"

    # brand gTLD
    assert data_rows["audi"][1] == "g"
    assert data_rows["audi"][2] == "true"

    # non-brand gTLD
    assert data_rows["com"][1] == "g"
    assert data_rows["com"][2] == "false"


def test_build_csv_rows_nic_url(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """NIC URL is nic.{zone}."""
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))

    rows = build_csv_rows(zones, brand_zones, {})
    data_rows = {row[0]: row for row in rows[1:]}

    assert data_rows["com"][4] == "nic.com"
    assert data_rows["uk"][4] == "nic.uk"


# --- generate_csv_report (I/O, writes to disk) ---


def test_csv_report_writes_file(test_zones_full_path: str, test_zones_brand_path: str) -> None:
    check_results = {"com": True, "org": True, "net": True, "uk": True, "de": True}

    with tempfile.TemporaryDirectory() as tmpdir:
        generate_csv_report(
            platform="Apple",
            check_results=check_results,
            zones_path=test_zones_full_path,
            brand_zones_path=test_zones_brand_path,
            output_dir=tmpdir,
        )

        report_path = Path(tmpdir) / "Report-Apple.csv"
        assert report_path.exists()

        content = report_path.read_text(encoding="utf-8")
        lines = content.strip().splitlines()

        # Check header
        assert lines[0] == "Zone,Type,Is a Brand?,Is linked?,NIC URL"

        # Check that linked zones show checkmark, unlinked show X
        for line in lines[1:]:
            cols = line.split(",")
            assert len(cols) == 5
            zone = cols[0]
            if zone in ("com", "org", "net", "uk", "de"):
                assert "\u2705" in cols[3]  # checkmark
            else:
                assert "\u274c" in cols[3]  # X mark


# --- generate_summary (accepts zone data directly) ---


def test_generate_summary_with_zone_data(
    test_zones_full_path: str,
    test_zones_brand_path: str,
    capsys,
) -> None:
    """generate_summary accepts zones and brand_zones directly."""
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))
    check_results = {"com": True, "org": True, "uk": True}

    generate_summary("Apple", check_results, zones=zones, brand_zones=brand_zones)

    captured = capsys.readouterr()
    assert "Apple platforms stdlib" in captured.out
    assert "Auto-linked zones" in captured.out


def test_summary_format() -> None:
    summary = ZoneSummary(
        total_zones=100,
        cctld_count=20,
        gtld_count=80,
        gtld_brand_count=30,
        gtld_non_brand_count=50,
        cctld_linked=10,
        gtld_linked=15,
        gtld_brand_linked=5,
        gtld_non_brand_linked=10,
    )

    output = format_summary(summary, "Apple")
    assert "Apple platforms stdlib" in output
    assert "100" in output
    assert "gTLDs" in output
    assert "ccTLDs" in output
    assert "Auto-linked zones" in output
