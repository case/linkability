"""AOSP reference mapping for Android platform checks.

Maps Android major versions to their canonical AOSP git tags. Used by
AndroidCheck and CLI commands to resolve version numbers to fetchable refs.

To add a new Android version, append an entry here and run:
    uv run linkability report csv --platform android --ref <version>
"""

from __future__ import annotations

# Ordered from oldest to newest. Each entry maps an Android version to a
# canonical AOSP git tag. History starts at Android 4 (2012), when ICANN's
# new gTLD program began delegating TLDs to the DNS.
ANDROID_REFS: dict[str, str] = {
    "4": "android-4.0.4_r1",
    "4.1": "android-4.1.2_r1",
    "4.2": "android-4.2.2_r1",
    "4.3": "android-4.3.1_r1",
    "4.4": "android-4.4.4_r1",
    "5": "android-5.0.2_r1",
    "5.1": "android-5.1.1_r1",
    "6": "android-6.0.1_r1",
    "7": "android-7.0.0_r1",
    "7.1": "android-7.1.2_r1",
    "8": "android-8.0.0_r1",
    "8.1": "android-8.1.0_r1",
    "9": "android-9.0.0_r1",
    "10": "android-10.0.0_r1",
    "11": "android-11.0.0_r1",
    "12": "android-12.0.0_r1",
    "12.1": "android-12.1.0_r1",
    "13": "android-13.0.0_r1",
    "14": "android-14.0.0_r1",
    "15": "android-15.0.0_r1",
    "16": "android-16.0.0_r1",
}

# The version used when no --ref is specified
DEFAULT_VERSION = "16"


def resolve_ref(ref: str) -> str:
    """Resolve a ref string to an AOSP git tag.

    Accepts either a major version number ("16") or a full AOSP tag
    ("android-16.0.0_r1"). Returns the full tag.
    """
    if ref in ANDROID_REFS:
        return ANDROID_REFS[ref]
    return ref
