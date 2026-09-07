"""Android platform check — parses AOSP Patterns.java TLD regex."""

from __future__ import annotations

import base64
import re
import sys
import urllib.error
import urllib.request
from typing import override

from .android_refs import ANDROID_REFS, ANDROID_RELEASE_DATES, DEFAULT_VERSION, resolve_ref
from .base import Check

_PATTERNS_PATH = "core/java/android/util/Patterns.java"


def parse_android_version(ref: str) -> str:
    """Extract Android version from an AOSP ref.

    Examples: "android-16.0.0_r1" → "16", "android-12.1.0_r1" → "12.1".
    Drops trailing ".0" to produce clean version strings.
    Falls back to the raw ref if the pattern doesn't match.
    """
    match = re.match(r"android-(\d+)\.(\d+)", ref)
    if not match:
        return ref
    major, minor = match.group(1), match.group(2)
    return f"{major}.{minor}" if minor != "0" else major


class AndroidCheck(Check):
    def __init__(self, aosp_ref: str | None = None) -> None:
        self._aosp_ref = resolve_ref(aosp_ref or DEFAULT_VERSION)
        self._cached_pattern: re.Pattern[str] | None = None

    @property
    @override
    def platform_name(self) -> str:
        return "Android"

    @property
    @override
    def platform_type(self) -> str:
        return "os"

    @property
    @override
    def platform_version(self) -> str:
        return parse_android_version(self._aosp_ref)

    @property
    @override
    def release_date(self) -> str | None:
        return ANDROID_RELEASE_DATES.get(self.platform_version)

    @property
    def aosp_ref(self) -> str:
        return self._aosp_ref

    @override
    def is_available(self) -> bool:
        return True  # Network-only, no device needed

    @override
    def check_zones(self, zones: list[str]) -> dict[str, bool]:
        pattern = self._get_android_pattern()
        return {zone: pattern.fullmatch(zone) is not None for zone in zones}

    def _get_android_pattern(self) -> re.Pattern[str]:
        if self._cached_pattern is not None:
            return self._cached_pattern
        source = fetch_patterns_java(self._aosp_ref)
        pattern = re.compile(extract_tld_regex(source))
        _check_pattern_baseline(pattern, self._aosp_ref)
        self._cached_pattern = pattern
        return pattern


def fetch_patterns_java(ref: str = ANDROID_REFS[DEFAULT_VERSION]) -> str:
    """Download Patterns.java from AOSP at the given ref, trying GitHub mirror first."""
    github_url = (
        f"https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base"
        f"/{ref}/{_PATTERNS_PATH}"
    )
    gitiles_url = (
        f"https://android.googlesource.com/platform/frameworks/base/"
        f"+/refs/tags/{ref}/{_PATTERNS_PATH}?format=TEXT"
    )
    sources = [
        (github_url, False),  # (url, is_base64)
        (gitiles_url, True),
    ]
    last_error = None
    for url, is_base64 in sources:
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                raw = response.read()
            if is_base64:
                return base64.b64decode(raw).decode("utf-8")
            return raw.decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last_error = (url, e)
            continue
    if last_error is None:
        raise ValueError("No sources configured to fetch Patterns.java")
    url, e = last_error
    if isinstance(e, urllib.error.HTTPError):
        print(f"Error: Could not fetch Patterns.java — HTTP {e.code} ({e.reason})")
    else:
        print(f"Error: Could not fetch Patterns.java — {e.reason}")
    print(f"Tried: {', '.join(u for u, _ in sources)}")
    sys.exit(1)


def extract_tld_regex(source: str) -> str:
    """Extract the TLD regex string constant from Patterns.java source.

    Tries IANA_TOP_LEVEL_DOMAINS (Android 7+) first, then falls back to
    TOP_LEVEL_DOMAIN_STR (Android 4–6).
    """
    # Try the newer constant first (Android 7+), then legacy (Android 4-6)
    match = re.search(r"IANA_TOP_LEVEL_DOMAINS\s*=\s*", source)
    if not match:
        match = re.search(r"TOP_LEVEL_DOMAIN_STR\s*=\s*", source)
    if not match:
        raise ValueError("Could not find TLD constant in Patterns.java source")

    # Collect all the quoted string fragments
    pos = match.end()
    fragments: list[str] = []
    while pos < len(source):
        # Skip whitespace, newlines, + signs, comments
        ws_match = re.match(r"[\s+]*(?://[^\n]*)?\s*", source[pos:])
        if ws_match:
            pos += ws_match.end()

        # Match a quoted string
        str_match = re.match(r'"((?:[^"\\]|\\.)*)"', source[pos:])
        if str_match:
            fragments.append(str_match.group(1))
            pos += str_match.end()
        else:
            break

    if not fragments:
        raise ValueError("Could not extract TLD regex strings")

    raw = "".join(fragments)
    # Unescape Java string escapes (e.g. \\- → -)
    return raw.replace("\\-", "-")


_BASELINE_TLDS = ("com", "net", "org")
# Underscored text alone would let a generic label pattern such as [a-z]{2,63}
# pass, so the second string is plausible-looking but not a delegated zone.
_BASELINE_NON_TLDS = ("", "invalid_tld_canary", "notarealtldxyzzy")


def _check_pattern_baseline(pattern: re.Pattern[str], ref: str) -> None:
    """Fail loudly if the pattern stopped behaving like a TLD list.

    A reshaped AOSP constant would otherwise publish 0% linkability silently.
    """
    for tld in _BASELINE_TLDS:
        if not pattern.fullmatch(tld):
            raise ValueError(f"AOSP TLD pattern for {ref} does not match baseline {tld!r}")
    for junk in _BASELINE_NON_TLDS:
        if pattern.fullmatch(junk):
            raise ValueError(f"AOSP TLD pattern for {ref} overmatches {junk!r}")
