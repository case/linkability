"""Tests for zone classification."""

from linkability.classify import classify_zone, is_cctld


def test_is_cctld() -> None:
    assert is_cctld("uk") is True
    assert is_cctld("de") is True
    assert is_cctld("au") is True
    assert is_cctld("us") is True


def test_is_not_cctld() -> None:
    assert is_cctld("com") is False  # 3 chars
    assert is_cctld("aero") is False  # 4 chars
    assert is_cctld("a") is False  # 1 char
    assert is_cctld("コム") is False  # non-ASCII 2-char


def test_classify_cctld() -> None:
    zone_type, is_brand = classify_zone("uk", {"google", "nike"})
    assert zone_type == "cc"
    assert is_brand is False


def test_classify_gtld_brand() -> None:
    zone_type, is_brand = classify_zone("google", {"google", "nike"})
    assert zone_type == "g"
    assert is_brand is True


def test_classify_gtld_non_brand() -> None:
    zone_type, is_brand = classify_zone("com", {"google", "nike"})
    assert zone_type == "g"
    assert is_brand is False
