"""Tests for Android check — regex parsing and expansion (hermetic, no network)."""

from linkability.checks.android import (
    AndroidCheck,
    expand_regex_to_tlds,
    extract_tld_regex,
    parse_android_version,
)
from linkability.checks.android_refs import ANDROID_REFS, ANDROID_RELEASE_DATES, resolve_ref


def test_expand_simple_alternatives() -> None:
    tlds = expand_regex_to_tlds("com|net|org")
    assert tlds == {"com", "net", "org"}


def test_expand_character_class() -> None:
    tlds = expand_regex_to_tlds("a[cde]")
    assert tlds == {"ac", "ad", "ae"}


def test_expand_character_range() -> None:
    tlds = expand_regex_to_tlds("a[a-c]")
    assert tlds == {"aa", "ab", "ac"}


def test_expand_mixed() -> None:
    tlds = expand_regex_to_tlds("com|a[cd]|net")
    assert tlds == {"com", "ac", "ad", "net"}


def test_expand_non_capturing_group() -> None:
    tlds = expand_regex_to_tlds("(?:com|net)")
    assert tlds == {"com", "net"}


def test_expand_nested_groups() -> None:
    tlds = expand_regex_to_tlds("(?:com|(?:net|org))")
    assert tlds == {"com", "net", "org"}


def test_expand_capturing_group() -> None:
    """Capturing groups (not just (?:...)) appear in older AOSP versions."""
    tlds = expand_regex_to_tlds("(com|net)")
    assert tlds == {"com", "net"}


def test_expand_group_with_suffix() -> None:
    tlds = expand_regex_to_tlds("(?:a|b)c")
    assert tlds == {"ac", "bc"}


def test_expand_mixed_range_and_literal_in_class() -> None:
    """Character class with both a range and standalone literals."""
    tlds = expand_regex_to_tlds("[a-ce]")
    assert tlds == {"a", "b", "c", "e"}



def test_extract_tld_regex() -> None:
    # Simplified mock of the Patterns.java constant
    source = '''
    static final String IANA_TOP_LEVEL_DOMAINS = "(?:"
        + "com|net|org"
        + ")";
    '''
    regex = extract_tld_regex(source)
    assert "com" in regex
    assert "net" in regex
    assert "org" in regex


def test_full_pipeline_with_mock_source() -> None:
    source = '''
    public static final String IANA_TOP_LEVEL_DOMAINS = "(?:"
        + "com|net|org|a[cd]"
        + ")";
    '''
    regex = extract_tld_regex(source)
    tlds = expand_regex_to_tlds(regex)
    assert "com" in tlds
    assert "net" in tlds
    assert "org" in tlds
    assert "ac" in tlds
    assert "ad" in tlds


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
    for ver in ["4", "4.1", "5", "6", "7", "8", "9", "10", "11", "12", "12.1", "13", "14", "15", "16"]:
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
