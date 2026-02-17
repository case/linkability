"""Tests for validation checks."""

import tempfile

from linkability.validate import show_missing_brands, test_cctld_brands


def test_show_missing_brands(
    test_zones_full_path: str,
    test_zones_brand_path: str,
    capsys,
) -> None:
    show_missing_brands(test_zones_full_path, test_zones_brand_path)
    captured = capsys.readouterr()
    # All test brand zones should be in the test full zone file
    assert "Delegated brands missing from root zone: 0" in captured.out


def test_cctld_brands_pass(capsys) -> None:
    # Create a CSV with no ccTLD brands (correct)
    csv_content = (
        "Zone,Type,Is a Brand?,Is linked?,NIC URL\n"
        "com,g,false,✅,nic.com\n"
        "uk,cc,false,✅,nic.uk\n"
        "google,g,true,❌,nic.google\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        f.flush()
        test_cctld_brands(f.name)

    captured = capsys.readouterr()
    assert "PASS" in captured.out


def test_cctld_brands_fail(capsys) -> None:
    # Create a CSV with a ccTLD marked as brand (incorrect)
    csv_content = (
        "Zone,Type,Is a Brand?,Is linked?,NIC URL\n"
        "com,g,false,✅,nic.com\n"
        "uk,ccTLD,true,✅,nic.uk\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        f.flush()
        test_cctld_brands(f.name)

    captured = capsys.readouterr()
    assert "FAIL" in captured.out
