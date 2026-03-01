"""Android platform check — parses AOSP Patterns.java TLD regex."""

from __future__ import annotations

import base64
import re
import sys
import urllib.error
import urllib.request

from .base import Check

_PATTERNS_PATH = "core/java/android/util/Patterns.java"

# GitHub mirror (plain text) — primary source, more reliable
_GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base"
    f"/master/{_PATTERNS_PATH}"
)

# AOSP Gitiles (base64-encoded) — fallback
_GITILES_URL = (
    "https://android.googlesource.com/platform/frameworks/base/"
    f"+/refs/heads/main/{_PATTERNS_PATH}?format=TEXT"
)


class AndroidCheck(Check):
    def __init__(self) -> None:
        self._cached_tlds: set[str] | None = None

    @property
    def platform_name(self) -> str:
        return "Android"

    @property
    def platform_type(self) -> str:
        return "os"

    @property
    def platform_version(self) -> str:
        return "main"

    def is_available(self) -> bool:
        return True  # Network-only, no device needed

    def check_zones(self, zones: list[str]) -> dict[str, bool]:
        tlds = self._get_android_tlds()
        return {zone: zone in tlds for zone in zones}

    def _get_android_tlds(self) -> set[str]:
        if self._cached_tlds is not None:
            return self._cached_tlds
        source = fetch_patterns_java()
        regex_str = extract_tld_regex(source)
        self._cached_tlds = expand_regex_to_tlds(regex_str)
        return self._cached_tlds


def fetch_patterns_java() -> str:
    """Download Patterns.java from AOSP, trying GitHub mirror first."""
    sources = [
        (_GITHUB_RAW_URL, False),  # (url, is_base64)
        (_GITILES_URL, True),
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
    """Extract the IANA_TOP_LEVEL_DOMAINS string constant from Patterns.java source."""
    # Find the start of the assignment
    match = re.search(r"IANA_TOP_LEVEL_DOMAINS\s*=\s*", source)
    if not match:
        raise ValueError("Could not find IANA_TOP_LEVEL_DOMAINS in source")

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

    return "".join(fragments)


def expand_regex_to_tlds(regex_str: str) -> set[str]:
    """Expand a regex-style TLD list into individual TLD strings.

    Handles patterns like:
    - Simple alternatives: "com|net|org"
    - Character class expansion: "a[cdefg]" -> ac, ad, ae, af, ag
    - Nested groups: "(?:com|net)"
    """
    # Remove outer non-capturing group wrapper if present
    regex_str = regex_str.strip()
    if regex_str.startswith("(?:") and regex_str.endswith(")"):
        # Check this is truly the outer wrapper (balanced parens)
        depth = 0
        is_outer = True
        for i, ch in enumerate(regex_str):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(regex_str) - 1:
                is_outer = False
                break
        if is_outer:
            regex_str = regex_str[3:-1]

    tlds: set[str] = set()
    _expand_alternatives(regex_str, tlds)
    return tlds


def _expand_alternatives(expr: str, result: set[str]) -> None:
    """Split on top-level | and expand each alternative."""
    alternatives = _split_top_level(expr, "|")
    for alt in alternatives:
        _expand_single(alt.strip(), result)


def _split_top_level(expr: str, delimiter: str) -> list[str]:
    """Split expression on delimiter, respecting parentheses and brackets."""
    parts: list[str] = []
    depth = 0
    bracket = False
    current: list[str] = []

    for ch in expr:
        if ch == "[" and not bracket:
            bracket = True
            current.append(ch)
        elif ch == "]" and bracket:
            bracket = False
            current.append(ch)
        elif ch == "(" and not bracket:
            depth += 1
            current.append(ch)
        elif ch == ")" and not bracket:
            depth -= 1
            current.append(ch)
        elif ch == delimiter and depth == 0 and not bracket:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)

    parts.append("".join(current))
    return parts


def _expand_single(alt: str, result: set[str]) -> None:
    """Expand a single alternative (no top-level |) into TLD strings."""
    if not alt:
        return

    # Handle non-capturing groups: (?:...) followed by optional suffix
    if alt.startswith("(?:"):
        # Find the matching closing paren
        depth = 0
        end = -1
        for i, ch in enumerate(alt):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            return

        inner = alt[3:end]
        suffix = alt[end + 1 :]

        # Expand inner alternatives
        inner_alts = _split_top_level(inner, "|")
        for ia in inner_alts:
            _expand_single(ia + suffix, result)
        return

    # Handle character classes: prefix[chars]suffix
    bracket_match = re.search(r"\[([^\]]+)\]", alt)
    if bracket_match:
        prefix = alt[: bracket_match.start()]
        chars = bracket_match.group(1)
        suffix = alt[bracket_match.end() :]

        # Expand character ranges like a-z
        expanded_chars = _expand_char_class(chars)
        for ch in expanded_chars:
            _expand_single(prefix + ch + suffix, result)
        return

    # Plain string — it's a TLD
    # Strip any remaining regex artifacts
    clean = alt.strip()
    if clean and re.match(r"^[a-z0-9\u0080-\uffff]+$", clean):
        result.add(clean)


def _expand_char_class(chars: str) -> list[str]:
    """Expand a character class string like 'a-df' into individual characters."""
    result: list[str] = []
    i = 0
    while i < len(chars):
        if i + 2 < len(chars) and chars[i + 1] == "-":
            start = ord(chars[i])
            end = ord(chars[i + 2])
            for c in range(start, end + 1):
                result.append(chr(c))
            i += 3
        else:
            result.append(chars[i])
            i += 1
    return result
