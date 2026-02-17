"""Apple platform check — delegates to a minimal Swift binary using NSDataDetector."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .base import Check

# Path to the Swift check package, relative to the project root
_CHECK_DIR = Path(__file__).resolve().parent.parent.parent.parent / "checks" / "apple"


class AppleCheck(Check):
    @property
    def platform_name(self) -> str:
        return "Apple"

    def is_available(self) -> bool:
        return sys.platform == "darwin"

    def _binary_path(self) -> Path:
        return _CHECK_DIR / ".build" / "release" / "AppleCheck"

    def _ensure_built(self) -> Path:
        binary = self._binary_path()
        if not binary.exists():
            print("Building Apple check binary...")
            subprocess.run(
                ["swift", "build", "-c", "release"],
                cwd=_CHECK_DIR,
                check=True,
            )
        return binary

    def check_zones(self, zones: list[str]) -> dict[str, bool]:
        if not self.is_available():
            raise RuntimeError("Apple check is only available on macOS")

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
