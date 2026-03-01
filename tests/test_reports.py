"""Tests for report generation."""

import json
import tempfile
from pathlib import Path

from linkability.reports import build_csv_rows, format_summary, generate_summary
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
    assert rows[0] == ["Zone", "Type", "Brand", "AutoLinked"]
    assert len(rows) == len(zones) + 1  # header + one per zone


def test_build_csv_rows_linked_values(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """Linked zones get 'true', unlinked get 'false'."""
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))
    check_results = {"com": True, "uk": True}

    rows = build_csv_rows(zones, brand_zones, check_results)
    data_rows = {row[0]: row for row in rows[1:]}

    assert data_rows["com"][3] == "true"
    assert data_rows["uk"][3] == "true"
    assert data_rows["org"][3] == "false"
    assert data_rows["audi"][3] == "false"


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
    assert data_rows["uk"][1] == "cctld"
    assert data_rows["uk"][2] == "false"

    # brand gTLD
    assert data_rows["audi"][1] == "gtld"
    assert data_rows["audi"][2] == "true"

    # non-brand gTLD
    assert data_rows["com"][1] == "gtld"
    assert data_rows["com"][2] == "false"


def test_build_csv_rows_no_nic_url_column(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """New format has exactly 4 columns, no NIC URL."""
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))

    rows = build_csv_rows(zones, brand_zones, {})
    for row in rows:
        assert len(row) == 4


# --- write_snapshot (writes snapshot CSV to disk) ---


def test_write_snapshot_creates_file(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """write_snapshot writes CSV to snapshots/{platform}/{version}.csv."""
    from linkability.reports import write_snapshot

    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))
    rows = build_csv_rows(zones, brand_zones, {"com": True})

    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_snapshot("apple", "15.3", rows, output_dir=tmpdir)

        assert path.exists()
        assert path == Path(tmpdir) / "snapshots" / "apple" / "15.3.csv"

        content = path.read_text(encoding="utf-8")
        lines = content.strip().splitlines()
        assert lines[0] == "Zone,Type,Brand,AutoLinked"
        assert len(lines) == len(zones) + 1


def test_write_snapshot_overwrites_existing(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    """Running twice with same version overwrites the file."""
    from linkability.reports import write_snapshot

    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))
    rows1 = build_csv_rows(zones, brand_zones, {"com": True})
    rows2 = build_csv_rows(zones, brand_zones, {"com": True, "org": True})

    with tempfile.TemporaryDirectory() as tmpdir:
        write_snapshot("apple", "15.3", rows1, output_dir=tmpdir)
        path = write_snapshot("apple", "15.3", rows2, output_dir=tmpdir)

        content = path.read_text(encoding="utf-8")
        data_rows = {
            line.split(",")[0]: line.split(",")
            for line in content.strip().splitlines()[1:]
        }
        assert data_rows["org"][3] == "true"


# --- build_manifest_entry (pure computation) ---


def test_build_manifest_entry() -> None:
    """build_manifest_entry returns a dict with all expected fields."""
    from linkability.reports import build_manifest_entry

    zones = ["com", "org", "uk", "de", "audi"]
    brand_zones = {"audi"}
    check_results = {"com": True, "uk": True, "audi": True}

    entry = build_manifest_entry(
        platform="apple",
        platform_type="os",
        version="15.3",
        check_date="2026-03-01",
        file_rel="apple/15.3.csv",
        zones=zones,
        brand_zones=brand_zones,
        check_results=check_results,
    )

    assert entry["platform"] == "apple"
    assert entry["platform_type"] == "os"
    assert entry["platform_version"] == "15.3"
    assert entry["check_date"] == "2026-03-01"
    assert entry["file"] == "apple/15.3.csv"
    assert entry["zones_count"] == 5
    assert entry["cctld_count"] == 2  # uk, de
    assert entry["gtld_count"] == 3  # com, org, audi
    assert entry["brand_count"] == 1  # audi
    assert entry["linked_total"] == 3  # com, uk, audi
    assert entry["linked_cctlds"] == 1  # uk
    assert entry["linked_gtlds"] == 2  # com, audi
    assert entry["linked_brands"] == 1  # audi


# --- load_manifest / save_manifest (I/O) ---


def test_load_manifest_missing_file() -> None:
    """load_manifest returns empty list if manifest.json doesn't exist."""
    from linkability.reports import load_manifest

    with tempfile.TemporaryDirectory() as tmpdir:
        entries = load_manifest(output_dir=tmpdir)
        assert entries == []


def test_save_and_load_manifest() -> None:
    """save_manifest writes JSON that load_manifest can read back."""
    from linkability.reports import load_manifest, save_manifest

    entries = [
        {
            "platform": "apple",
            "platform_version": "15.3",
            "zones_count": 100,
        }
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        save_manifest(entries, output_dir=tmpdir)

        manifest_path = Path(tmpdir) / "manifest.json"
        assert manifest_path.exists()

        loaded = load_manifest(output_dir=tmpdir)
        assert loaded == entries

        # Verify JSON structure
        data = json.loads(manifest_path.read_text())
        assert "snapshots" in data
        assert data["snapshots"] == entries


def test_save_manifest_updates_existing_version() -> None:
    """Saving a manifest with an existing platform+version replaces the entry."""
    from linkability.reports import load_manifest, save_manifest

    entries = [
        {"platform": "apple", "platform_version": "15.3", "linked_total": 100},
        {"platform": "android", "platform_version": "14", "linked_total": 200},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        save_manifest(entries, output_dir=tmpdir)
        loaded = load_manifest(output_dir=tmpdir)
        assert len(loaded) == 2


# --- build_summary_csv (pure computation) ---


def test_build_summary_csv_header() -> None:
    """build_summary_csv returns header as first row."""
    from linkability.reports import build_summary_csv

    rows = build_summary_csv([])
    assert rows[0] == [
        "platform", "platform_type", "platform_version", "check_date",
        "zones_count", "cctld_count", "gtld_count", "brand_count",
        "linked_total", "linked_cctlds", "linked_gtlds", "linked_brands",
        "linked_pct",
    ]


def test_build_summary_csv_data_row() -> None:
    """build_summary_csv converts manifest entries to summary rows."""
    from linkability.reports import build_summary_csv

    entries = [
        {
            "platform": "apple",
            "platform_type": "os",
            "platform_version": "15.3",
            "check_date": "2026-03-01",
            "zones_count": 100,
            "cctld_count": 20,
            "gtld_count": 80,
            "brand_count": 30,
            "linked_total": 50,
            "linked_cctlds": 10,
            "linked_gtlds": 40,
            "linked_brands": 5,
        }
    ]

    rows = build_summary_csv(entries)
    assert len(rows) == 2  # header + 1 data row
    assert rows[1] == [
        "apple", "os", "15.3", "2026-03-01",
        "100", "20", "80", "30",
        "50", "10", "40", "5",
        "50.0",
    ]


# --- save_summary_csv (I/O) ---


def test_save_summary_csv_writes_file() -> None:
    """save_summary_csv writes a CSV file."""
    from linkability.reports import save_summary_csv

    entries = [
        {
            "platform": "apple",
            "platform_type": "os",
            "platform_version": "15.3",
            "check_date": "2026-03-01",
            "zones_count": 100,
            "cctld_count": 20,
            "gtld_count": 80,
            "brand_count": 30,
            "linked_total": 50,
            "linked_cctlds": 10,
            "linked_gtlds": 40,
            "linked_brands": 5,
        }
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        save_summary_csv(entries, output_dir=tmpdir)

        summary_path = Path(tmpdir) / "summary.csv"
        assert summary_path.exists()

        content = summary_path.read_text(encoding="utf-8")
        lines = content.strip().splitlines()
        assert lines[0].startswith("platform,")
        assert "apple" in lines[1]


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
