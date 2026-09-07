"""Electron/Chromium platform check (stub).

Chromium uses the Public Suffix List (PSL) from publicsuffix.org.
Future approach: download PSL, parse bare TLD entries (no dots), compare against IANA.
"""

from __future__ import annotations

from typing import override

from .base import Check


class ElectronCheck(Check):
    @property
    @override
    def platform_name(self) -> str:
        return "Electron"

    @property
    @override
    def platform_type(self) -> str:
        return "framework"

    @property
    @override
    def platform_version(self) -> str:
        return "unknown"

    @override
    def is_available(self) -> bool:
        return False

    @override
    def check_zones(self, zones: list[str]) -> dict[str, bool]:
        raise NotImplementedError(
            "Electron check not yet implemented. "
            "Planned approach: parse Public Suffix List from publicsuffix.org."
        )
