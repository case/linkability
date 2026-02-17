"""Tests for report generation."""

import tempfile
from pathlib import Path

from linkability.reports import format_summary, generate_csv_report
from linkability.analyze import ZoneSummary


def test_csv_format(test_zones_full_path: str, test_zones_brand_path: str) -> None:
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
