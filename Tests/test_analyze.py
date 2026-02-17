"""Tests for zone summary analysis."""

from linkability.analyze import ZoneSummary, compute_summary
from linkability.zones import read_zones


def test_zone_summary_percentage_calculations() -> None:
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

    assert abs(summary.cctld_percentage_of_total - 20.0) < 0.1
    assert abs(summary.gtld_percentage_of_total - 80.0) < 0.1
    assert abs(summary.gtld_brand_percentage_of_gtld - 37.5) < 0.1  # 30/80 * 100
    assert abs(summary.gtld_brand_percentage_of_total - 30.0) < 0.1

    assert abs(summary.cctld_linkable_percentage - 50.0) < 0.1  # 10/20 * 100
    assert abs(summary.gtld_linkable_percentage - 18.75) < 0.1  # 15/80 * 100
    assert abs(summary.gtld_non_brand_linkable_percentage - 20.0) < 0.1  # 10/50 * 100

    assert summary.total_linked_zones == 25  # 10 + 15
    assert abs(summary.total_linked_percentage - 25.0) < 0.1  # 25/100 * 100


def test_zone_summary_zero_division() -> None:
    summary = ZoneSummary(
        total_zones=0,
        cctld_count=0,
        gtld_count=0,
        gtld_brand_count=0,
        gtld_non_brand_count=0,
        cctld_linked=0,
        gtld_linked=0,
        gtld_brand_linked=0,
        gtld_non_brand_linked=0,
    )

    assert summary.cctld_percentage_of_total == 0.0
    assert summary.gtld_percentage_of_total == 0.0
    assert summary.gtld_brand_percentage_of_gtld == 0.0
    assert summary.cctld_linkable_percentage == 0.0
    assert summary.gtld_linkable_percentage == 0.0
    assert summary.total_linked_percentage == 0.0


def test_zone_summary_consistency() -> None:
    summary = ZoneSummary(
        total_zones=100,
        cctld_count=25,
        gtld_count=75,
        gtld_brand_count=30,
        gtld_non_brand_count=45,
        cctld_linked=12,
        gtld_linked=18,
        gtld_brand_linked=8,
        gtld_non_brand_linked=10,
    )

    assert summary.cctld_count + summary.gtld_count == summary.total_zones
    assert summary.gtld_brand_count + summary.gtld_non_brand_count == summary.gtld_count
    assert summary.gtld_brand_linked + summary.gtld_non_brand_linked == summary.gtld_linked
    assert summary.cctld_linked + summary.gtld_linked == summary.total_linked_zones


def test_zone_summary_all_linked() -> None:
    summary = ZoneSummary(
        total_zones=10,
        cctld_count=4,
        gtld_count=6,
        gtld_brand_count=2,
        gtld_non_brand_count=4,
        cctld_linked=4,
        gtld_linked=6,
        gtld_brand_linked=2,
        gtld_non_brand_linked=4,
    )

    assert abs(summary.cctld_linkable_percentage - 100.0) < 0.1
    assert abs(summary.gtld_linkable_percentage - 100.0) < 0.1
    assert abs(summary.total_linked_percentage - 100.0) < 0.1


def test_zone_summary_none_linked() -> None:
    summary = ZoneSummary(
        total_zones=10,
        cctld_count=4,
        gtld_count=6,
        gtld_brand_count=2,
        gtld_non_brand_count=4,
        cctld_linked=0,
        gtld_linked=0,
        gtld_brand_linked=0,
        gtld_non_brand_linked=0,
    )

    assert abs(summary.cctld_linkable_percentage - 0.0) < 0.1
    assert abs(summary.gtld_linkable_percentage - 0.0) < 0.1
    assert abs(summary.total_linked_percentage - 0.0) < 0.1


def test_compute_summary_with_test_data(
    test_zones_full_path: str,
    test_zones_brand_path: str,
) -> None:
    zones = read_zones(test_zones_full_path)
    brand_zones = set(read_zones(test_zones_brand_path))

    assert len(zones) > 0
    assert len(brand_zones) > 0

    # Create mock check results — mark com, org, net, uk, de as linked
    check_results = {zone: zone in {"com", "org", "net", "uk", "de"} for zone in zones}

    summary = compute_summary(zones, brand_zones, check_results)

    # Validate expected structure based on test data:
    # ccTLDs: au, de, uk (3 total)
    # gTLDs: audi, bmw, com, google, microsoft, net, nike, org, test, vermögensberater, コム (11)
    # Brand gTLDs: audi, bmw, google, microsoft, nike (5 total)
    # Non-brand gTLDs: com, net, org, test, vermögensberater, コム (6 total)
    assert summary.total_zones == 14
    assert summary.cctld_count == 3
    assert summary.gtld_count == 11
    assert summary.gtld_brand_count == 5
    assert summary.gtld_non_brand_count == 6

    assert summary.cctld_count + summary.gtld_count == summary.total_zones
    assert summary.gtld_brand_count + summary.gtld_non_brand_count == summary.gtld_count

    expected_cctld_pct = 3.0 / 14.0 * 100.0
    expected_gtld_pct = 11.0 / 14.0 * 100.0
    assert abs(summary.cctld_percentage_of_total - expected_cctld_pct) < 0.1
    assert abs(summary.gtld_percentage_of_total - expected_gtld_pct) < 0.1
