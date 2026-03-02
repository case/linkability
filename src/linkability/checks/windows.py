"""Windows platform check — delegates to a .NET binary using RichEdit EM_AUTOURLDETECT."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .base import Check
from .windows_refs import WINDOWS_BUILD_MAP, WINDOWS_RELEASE_DATES

# Path to the .NET check project, relative to the project root
_CHECK_DIR = Path(__file__).resolve().parent.parent.parent.parent / "checks" / "windows"


def _detect_windows_version() -> str:
    """Detect Windows consumer version from the registry build number."""
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


class WindowsCheck(Check):
    @property
    def platform_name(self) -> str:
        return "Windows"

    @property
    def platform_type(self) -> str:
        return "os"

    @property
    def platform_version(self) -> str:
        if sys.platform != "win32":
            return "unknown"
        return _detect_windows_version()

    @property
    def release_date(self) -> str | None:
        return WINDOWS_RELEASE_DATES.get(self.platform_version)

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
            check=True,
        )

        data = json.loads(result.stdout)
        return data["results"]
