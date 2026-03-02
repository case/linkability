"""Abstract base class for platform checks."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Check(ABC):
    """Base class for platform link-detection checks."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform name (e.g. 'Apple')."""

    @property
    @abstractmethod
    def platform_type(self) -> str:
        """Platform category: 'os', 'browser', 'framework', or 'app'."""

    @property
    @abstractmethod
    def platform_version(self) -> str:
        """Platform version string, detected at runtime."""

    @property
    def release_date(self) -> str | None:
        """Release date of this platform version (YYYY-MM-DD), or None if unknown."""
        return None

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this check can run on the current system."""

    @abstractmethod
    def check_zones(self, zones: list[str]) -> dict[str, bool]:
        """Test each zone and return {zone: is_linked} results."""
