"""Tests for Android check: regex extraction and zone matching (hermetic, no network)."""

import pytest

from linkability.checks.android import (
    AndroidCheck,
    extract_tld_regex,
    parse_android_version,
)
from linkability.checks.android_refs import ANDROID_REFS, ANDROID_RELEASE_DATES, resolve_ref

MODERN_CONST = "IANA_TOP_LEVEL_DOMAINS"
LEGACY_CONST = "TOP_LEVEL_DOMAIN_STR"


def _java_source(const: str, regex: str) -> str:
    """Build a minimal Patterns.java fragment declaring one TLD constant."""
    return f'''
    public static final String {const} = "{regex}";
    '''


def _checker(monkeypatch: pytest.MonkeyPatch, const: str, body: str, ref: str) -> AndroidCheck:
    monkeypatch.setattr(
        "linkability.checks.android.fetch_patterns_java",
        lambda _ref: _java_source(const, body),
    )
    return AndroidCheck(aosp_ref=ref)


# --- Regex extraction ---


def test_extract_tld_regex() -> None:
    regex = extract_tld_regex(_java_source(MODERN_CONST, "(?:com|net|org)"))
    assert regex == "(?:com|net|org)"


def test_extract_tld_regex_legacy_fallback() -> None:
    """Android 4-6 declare TOP_LEVEL_DOMAIN_STR; 8 of the 21 refs use it."""
    regex = extract_tld_regex(_java_source(LEGACY_CONST, "(?:com|net|a[cd])"))
    assert regex == "(?:com|net|a[cd])"


def test_extract_tld_regex_missing_constant() -> None:
    with pytest.raises(ValueError, match="Could not find TLD constant"):
        extract_tld_regex("public class Patterns { }")


def test_extract_tld_regex_missing_strings() -> None:
    with pytest.raises(ValueError, match="Could not extract TLD regex strings"):
        extract_tld_regex(f"static final String {MODERN_CONST} = ;")


# --- Zone matching, through the public check ---

# Each fragment is embedded in a baseline-complete pattern so the drift canary
# passes. Cases carry over the constructs the deleted expansion tests covered.
CONSTRUCT_CASES = [
    ("simple_alternatives", "", ["com", "net", "org"], ["comm", "xcom", "co"]),
    ("character_class", "|a[cde]", ["ac", "ad", "ae"], ["ab", "af", "a"]),
    ("character_range", "|b[a-c]", ["ba", "bb", "bc"], ["bd", "b"]),
    ("non_capturing_group", "|(?:xy|xz)", ["xy", "xz"], ["x", "xyz"]),
    ("nested_groups", "|(?:pq|(?:qr|rs))", ["pq", "qr", "rs"], ["p", "qrs"]),
    ("capturing_group", "|(st|tu)", ["st", "tu"], ["s", "stu"]),
    ("group_with_suffix", "|(?:u|v)w", ["uw", "vw"], ["u", "uvw"]),
    ("mixed_range_and_literal_in_class", "|[x-ze]", ["x", "y", "z", "e"], ["w", "xy"]),
]


@pytest.mark.parametrize(
    ("fragment", "positives", "negatives"),
    [pytest.param(f, p, n, id=i) for i, f, p, n in CONSTRUCT_CASES],
)
@pytest.mark.parametrize("const", [MODERN_CONST, LEGACY_CONST])
def test_check_zones_matches_aosp_constructs(
    monkeypatch: pytest.MonkeyPatch,
    const: str,
    fragment: str,
    positives: list[str],
    negatives: list[str],
) -> None:
    """Capturing groups and bare classes appear in older AOSP versions."""
    check = _checker(monkeypatch, const, f"(?:com|net|org{fragment})", "android-16.0.0_r1")
    results = check.check_zones(positives + negatives)
    assert results == {z: True for z in positives} | {z: False for z in negatives}


def test_check_zones_requires_whole_string_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """fullmatch, not match or search: prefixes and suffixes must not count."""
    check = _checker(monkeypatch, MODERN_CONST, "(?:com|net|org)", "android-16.0.0_r1")
    assert check.check_zones(["com", "comm", "xcom", "xcomx", "com\n"]) == {
        "com": True,
        "comm": False,
        "xcom": False,
        "xcomx": False,
        "com\n": False,
    }


# --- Drift canary ---


def test_check_zones_raises_when_baseline_tlds_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reshaped constant must fail loudly, not report every zone unlinked."""
    check = _checker(monkeypatch, MODERN_CONST, "(?:foo|bar)", "android-16.0.0_r1")
    with pytest.raises(ValueError, match="does not match baseline"):
        check.check_zones(["com"])


def test_check_zones_raises_when_pattern_overmatches(monkeypatch: pytest.MonkeyPatch) -> None:
    check = _checker(monkeypatch, MODERN_CONST, "(?:.*)", "android-16.0.0_r1")
    with pytest.raises(ValueError, match="overmatches"):
        check.check_zones(["com"])


@pytest.mark.parametrize(
    ("regex", "positives", "negatives"),
    [
        pytest.param("^(?:com|net|org)$", ["com", "org"], ["comm"], id="anchors"),
        pytest.param(r"(?:com|net|org|d[\d])", ["com", "d5"], ["d", "dx"], id="escape_class"),
    ],
)
def test_check_zones_accepts_benign_syntax_drift(
    monkeypatch: pytest.MonkeyPatch, regex: str, positives: list[str], negatives: list[str]
) -> None:
    """Anchors and escape classes are harmless under fullmatch; do not reject them."""
    check = _checker(monkeypatch, MODERN_CONST, regex, "android-16.0.0_r1")
    results = check.check_zones(positives + negatives)
    assert results == {z: True for z in positives} | {z: False for z in negatives}


def test_check_zones_raises_on_generic_label_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    """A generic label pattern matches com/net/org but carries no TLD list."""
    check = _checker(monkeypatch, MODERN_CONST, "[a-z]{2,63}", "android-16.0.0_r1")
    with pytest.raises(ValueError, match="overmatches"):
        check.check_zones(["com"])


def test_check_zones_reuses_cached_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    """report android-all calls check_zones per ref; refetching would hammer AOSP."""
    calls = 0

    def _counting_fetch(_ref: str) -> str:
        nonlocal calls
        calls += 1
        return _java_source(MODERN_CONST, "(?:com|net|org)")

    monkeypatch.setattr("linkability.checks.android.fetch_patterns_java", _counting_fetch)
    check = AndroidCheck(aosp_ref="android-16.0.0_r1")
    check.check_zones(["com"])
    check.check_zones(["net"])
    assert calls == 1


# --- Version parsing ---


def test_parse_android_version_standard_tag() -> None:
    assert parse_android_version("android-16.0.0_r1") == "16"


def test_parse_android_version_older_tags() -> None:
    assert parse_android_version("android-14.0.0_r1") == "14"
    assert parse_android_version("android-12.0.0_r1") == "12"


def test_parse_android_version_dot_release() -> None:
    assert parse_android_version("android-12.1.0_r1") == "12.1"


def test_parse_android_version_fallback() -> None:
    assert parse_android_version("main") == "main"
    assert parse_android_version("some-custom-ref") == "some-custom-ref"


# --- AndroidCheck parameterization ---


def test_android_check_default_ref() -> None:
    check = AndroidCheck()
    assert check.aosp_ref == "android-16.0.0_r1"
    assert check.platform_version == "16"


def test_android_check_custom_ref() -> None:
    check = AndroidCheck(aosp_ref="android-14.0.0_r1")
    assert check.aosp_ref == "android-14.0.0_r1"
    assert check.platform_version == "14"


def test_android_check_metadata() -> None:
    check = AndroidCheck(aosp_ref="android-15.0.0_r1")
    assert check.platform_name == "Android"
    assert check.platform_type == "os"
    assert check.platform_version == "15"


def test_android_check_short_version() -> None:
    check = AndroidCheck(aosp_ref="14")
    assert check.aosp_ref == "android-14.0.0_r1"
    assert check.platform_version == "14"


# --- Ref mapping ---


def test_resolve_ref_short_version() -> None:
    assert resolve_ref("16") == "android-16.0.0_r1"
    assert resolve_ref("12") == "android-12.0.0_r1"


def test_resolve_ref_full_tag_passthrough() -> None:
    assert resolve_ref("android-16.0.0_r1") == "android-16.0.0_r1"
    assert resolve_ref("some-custom-ref") == "some-custom-ref"


def test_android_refs_has_expected_versions() -> None:
    for ver in [
        "4",
        "4.1",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
        "12.1",
        "13",
        "14",
        "15",
        "16",
    ]:
        assert ver in ANDROID_REFS


# --- Release dates ---


def test_android_release_dates_covers_all_versions() -> None:
    """Every version in ANDROID_REFS has a corresponding release date."""
    for version in ANDROID_REFS:
        assert version in ANDROID_RELEASE_DATES, f"Missing release date for Android {version}"


def test_android_release_dates_format() -> None:
    """Release dates are valid YYYY-MM-DD strings."""
    import re

    for version, date_str in ANDROID_RELEASE_DATES.items():
        assert re.match(r"\d{4}-\d{2}-\d{2}$", date_str), (
            f"Bad date format for Android {version}: {date_str}"
        )


def test_android_check_release_date() -> None:
    check = AndroidCheck(aosp_ref="14")
    assert check.release_date == "2023-10-04"


def test_android_check_release_date_unknown_ref() -> None:
    check = AndroidCheck(aosp_ref="some-custom-ref")
    assert check.release_date is None
