"""Abstract base class for platform checks."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Check(ABC):
    """Base class for platform link-detection checks."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform name (e.g. 'Apple')."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this check can run on the current system."""

    @abstractmethod
    def check_zones(self, zones: list[str]) -> dict[str, bool]:
        """Test each zone and return {zone: is_linked} results."""
