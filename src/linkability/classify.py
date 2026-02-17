"""Zone classification: ccTLD vs gTLD, brand detection."""

from __future__ import annotations


def is_cctld(zone: str) -> bool:
    """A ccTLD is exactly 2 ASCII characters."""
    return len(zone) == 2 and zone.isascii()


def classify_zone(zone: str, brand_zones: set[str]) -> tuple[str, bool]:
    """Return (type, is_brand) for a zone.

    type is "cc" for ccTLD or "g" for gTLD.
    Brands are only possible among gTLDs.
    """
    if is_cctld(zone):
        return ("cc", False)
    return ("g", zone in brand_zones)
