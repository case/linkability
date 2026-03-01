"""Tests for Android check — regex parsing and expansion (hermetic, no network)."""

from linkability.checks.android import (
    expand_regex_to_tlds,
    extract_tld_regex,
    _expand_char_class,
)


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


def test_expand_char_class_helper() -> None:
    assert _expand_char_class("ace") == ["a", "c", "e"]
    assert _expand_char_class("a-c") == ["a", "b", "c"]
    assert _expand_char_class("a-ce") == ["a", "b", "c", "e"]


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
