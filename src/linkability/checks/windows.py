"""Windows platform check — delegates to a .NET binary using RichEdit EM_AUTOURLDETECT."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import override

from .base import Check
from .windows_refs import WINDOWS_BUILD_MAP, WINDOWS_RELEASE_DATES

# Path to the .NET check project, relative to the project root
_CHECK_DIR = Path(__file__).resolve().parent.parent.parent.parent / "checks" / "windows"


def _detect_windows_version() -> str:
    """Detect Windows consumer version from the registry build number."""
    # Typeshed conditions the winreg stub on sys.platform, so the guard is what
    # lets a type checker resolve the registry calls off Windows.
    if sys.platform == "win32":
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        )
        try:
            build = winreg.QueryValueEx(key, "CurrentBuild")[0]
        finally:
            winreg.CloseKey(key)
        return WINDOWS_BUILD_MAP.get(build, f"Build-{build}")
    return "unknown"


class WindowsCheck(Check):
    @property
    @override
    def platform_name(self) -> str:
        return "Windows"

    @property
    @override
    def platform_type(self) -> str:
        return "os"

    @property
    @override
    def platform_version(self) -> str:
        return _detect_windows_version()

    @property
    @override
    def release_date(self) -> str | None:
        return WINDOWS_RELEASE_DATES.get(self.platform_version)

    @override
    def is_available(self) -> bool:
        return sys.platform == "win32"

    def _binary_path(self) -> Path:
        return _CHECK_DIR / "bin" / "Release" / "net8.0" / "WindowsCheck.exe"

    def _ensure_built(self) -> Path:
        binary = self._binary_path()
        if not binary.exists():
            print("Building Windows check binary...")
            subprocess.run(
                ["dotnet", "build", "-c", "Release"],
                cwd=_CHECK_DIR,
                check=True,
            )
        return binary

    @override
    def check_zones(self, zones: list[str]) -> dict[str, bool]:
        if not self.is_available():
            raise RuntimeError("Windows check is only available on Windows")

        binary = self._ensure_built()
        input_data = "\n".join(zones)

        result = subprocess.run(
            [str(binary)],
            input=input_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )

        # Print diagnostics (canary tests, etc.) from the binary.
        if result.stderr:
            print(result.stderr, end="")

        data = json.loads(result.stdout)
        return data["results"]
