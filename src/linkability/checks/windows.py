"""Windows platform check (stub).

Windows RichEdit control (EM_AUTOURLDETECT) has a limited hardcoded TLD list.
Requires a Windows machine + C#/PowerShell to test.
Future approach: create a small .NET check executable (same pattern as Apple Swift check).
"""

from __future__ import annotations

from .base import Check


class WindowsCheck(Check):
    @property
    def platform_name(self) -> str:
        return "Windows"

    @property
    def platform_type(self) -> str:
        return "os"

    @property
    def platform_version(self) -> str:
        return "unknown"

    def is_available(self) -> bool:
        return False

    def check_zones(self, zones: list[str]) -> dict[str, bool]:
        raise NotImplementedError(
            "Windows check not yet implemented. "
            "Planned approach: .NET executable testing RichEdit EM_AUTOURLDETECT."
        )
