"""Windows version mapping for platform checks.

Maps Windows build numbers to consumer-friendly version names and release dates.
Used by WindowsCheck to label reports with recognizable version identifiers.

The GH Actions runners are Server editions, but the RichEdit URL detection
behavior is the same as the consumer Windows of the corresponding generation:
  - Server 2022 (build 20348) → Windows 10 era
  - Server 2025 (build 26100) → Windows 11 (24H2)
"""

from __future__ import annotations

# Maps CurrentBuild registry value to consumer-friendly version name.
WINDOWS_BUILD_MAP: dict[str, str] = {
    "20348": "10",   # Windows Server 2022
    "26100": "11",   # Windows Server 2025
}

# Maps consumer version name to initial public release date (YYYY-MM-DD).
# Primary source: Wikipedia (Windows version history).
WINDOWS_RELEASE_DATES: dict[str, str] = {
    "10": "2015-07-29",  # Windows 10
    "11": "2021-10-05",  # Windows 11
}
