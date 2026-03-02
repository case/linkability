"""Apple release date mapping for macOS versions.

Maps macOS major version numbers to their initial public release dates.
Used by AppleCheck to annotate reports with OS release timelines.

To add a new macOS version, append an entry here when the version ships.
"""

from __future__ import annotations

# Maps macOS major version to its initial public release date (YYYY-MM-DD).
# Primary source: Wikipedia (macOS version history).
# Secondary: https://setapp.com/how-to/full-list-of-all-macos-versions
APPLE_RELEASE_DATES: dict[str, str] = {
    "14": "2023-09-26",  # macOS 14 Sonoma
    "15": "2024-09-16",  # macOS 15 Sequoia
    "26": "2025-09-15",  # macOS 26 Tahoe
}
