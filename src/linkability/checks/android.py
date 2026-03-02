"""Android platform check — parses AOSP Patterns.java TLD regex."""

from __future__ import annotations

import base64
import re
import re._constants as _rc
import re._parser as _rp
import sys
import urllib.error
import urllib.request

from .android_refs import DEFAULT_VERSION, ANDROID_REFS, resolve_ref
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
        self._cached_tlds: set[str] | None = None

    @property
    def platform_name(self) -> str:
        return "Android"

    @property
    def platform_type(self) -> str:
        return "os"

    @property
    def platform_version(self) -> str:
        return parse_android_version(self._aosp_ref)

    @property
    def aosp_ref(self) -> str:
        return self._aosp_ref

    def is_available(self) -> bool:
        return True  # Network-only, no device needed

    def check_zones(self, zones: list[str]) -> dict[str, bool]:
        tlds = self._get_android_tlds()
        return {zone: zone in tlds for zone in zones}

    def _get_android_tlds(self) -> set[str]:
        if self._cached_tlds is not None:
            return self._cached_tlds
        source = fetch_patterns_java(self._aosp_ref)
        regex_str = extract_tld_regex(source)
        self._cached_tlds = expand_regex_to_tlds(regex_str)
        return self._cached_tlds


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


def expand_regex_to_tlds(regex_str: str) -> set[str]:
    """Expand a regex-style TLD list into individual TLD strings.

    Uses Python's regex parser to build an AST, then recursively enumerates
    all matching strings.  This handles any combination of alternations,
    character classes, ranges, and groups — far more robustly than hand-rolling
    a regex-syntax walker.
    """
    parsed = _rp.parse(regex_str)
    return set(_enumerate_seq(parsed))


def _enumerate_seq(seq: _rp.SubPattern) -> list[str]:
    """Enumerate all strings matching a parsed regex sequence (concatenation)."""
    result = [""]
    for item in seq:
        options = _enumerate_item(item)
        result = [prefix + suffix for prefix in result for suffix in options]
    return result


def _enumerate_item(item: tuple) -> list[str]:
    """Enumerate all strings matching a single AST node."""
    opcode, av = item

    if opcode == _rc.LITERAL:
        return [chr(av)]

    if opcode == _rc.IN:
        chars: list[str] = []
        for op, val in av:
            if op == _rc.LITERAL:
                chars.append(chr(val))
            elif op == _rc.RANGE:
                lo, hi = val
                chars.extend(chr(c) for c in range(lo, hi + 1))
        return chars

    if opcode == _rc.BRANCH:
        # av is (None, [branch1, branch2, ...])
        results: list[str] = []
        for branch in av[1]:
            results.extend(_enumerate_seq(branch))
        return results

    if opcode == _rc.SUBPATTERN:
        # av is (group_id, add_flags, del_flags, pattern)
        return _enumerate_seq(av[-1])

    raise ValueError(f"Unsupported regex construct in TLD pattern: {opcode}")
