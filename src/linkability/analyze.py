"""Zone summary analysis — computes linkability statistics."""

from __future__ import annotations

from dataclasses import dataclass

from .classify import is_cctld


@dataclass
class ZoneSummary:
    total_zones: int
    cctld_count: int
    gtld_count: int
    gtld_brand_count: int
    gtld_non_brand_count: int
    cctld_linked: int
    gtld_linked: int
    gtld_brand_linked: int
    gtld_non_brand_linked: int

    @property
    def cctld_percentage_of_total(self) -> float:
        return self.cctld_count / self.total_zones * 100 if self.total_zones > 0 else 0.0

    @property
    def gtld_percentage_of_total(self) -> float:
        return self.gtld_count / self.total_zones * 100 if self.total_zones > 0 else 0.0

    @property
    def gtld_brand_percentage_of_gtld(self) -> float:
        return self.gtld_brand_count / self.gtld_count * 100 if self.gtld_count > 0 else 0.0

    @property
    def gtld_brand_percentage_of_total(self) -> float:
        return self.gtld_brand_count / self.total_zones * 100 if self.total_zones > 0 else 0.0

    @property
    def cctld_linkable_percentage(self) -> float:
        return self.cctld_linked / self.cctld_count * 100 if self.cctld_count > 0 else 0.0

    @property
    def gtld_non_brand_linkable_percentage(self) -> float:
        return (
            self.gtld_non_brand_linked / self.gtld_non_brand_count * 100
            if self.gtld_non_brand_count > 0
            else 0.0
        )

    @property
    def cctld_linked_percentage_of_total(self) -> float:
        return self.cctld_linked / self.total_zones * 100 if self.total_zones > 0 else 0.0

    @property
    def gtld_non_brand_linked_percentage_of_total(self) -> float:
        return self.gtld_non_brand_linked / self.total_zones * 100 if self.total_zones > 0 else 0.0

    @property
    def gtld_linkable_percentage(self) -> float:
        return self.gtld_linked / self.gtld_count * 100 if self.gtld_count > 0 else 0.0

    @property
    def gtld_linked_percentage_of_total(self) -> float:
        return self.gtld_linked / self.total_zones * 100 if self.total_zones > 0 else 0.0

    @property
    def total_linked_zones(self) -> int:
        return self.cctld_linked + self.gtld_linked

    @property
    def total_linked_percentage(self) -> float:
        return self.total_linked_zones / self.total_zones * 100 if self.total_zones > 0 else 0.0

    @property
    def gtld_brand_linkable_percentage(self) -> float:
        return (
            self.gtld_brand_linked / self.gtld_brand_count * 100
            if self.gtld_brand_count > 0
            else 0.0
        )

    @property
    def gtld_brand_linked_percentage_of_total(self) -> float:
        return self.gtld_brand_linked / self.total_zones * 100 if self.total_zones > 0 else 0.0


def compute_summary(
    zones: list[str],
    brand_zones: set[str],
    check_results: dict[str, bool],
) -> ZoneSummary:
    """Compute a ZoneSummary from zones, brand set, and per-zone check results."""
    cctld_count = 0
    gtld_count = 0
    gtld_brand_count = 0
    gtld_non_brand_count = 0
    cctld_linked = 0
    gtld_linked = 0
    gtld_brand_linked = 0
    gtld_non_brand_linked = 0

    for zone in zones:
        is_linked = check_results.get(zone, False)

        if is_cctld(zone):
            cctld_count += 1
            if is_linked:
                cctld_linked += 1
        else:
            gtld_count += 1
            if is_linked:
                gtld_linked += 1
            if zone in brand_zones:
                gtld_brand_count += 1
                if is_linked:
                    gtld_brand_linked += 1
            else:
                gtld_non_brand_count += 1
                if is_linked:
                    gtld_non_brand_linked += 1

    return ZoneSummary(
        total_zones=len(zones),
        cctld_count=cctld_count,
        gtld_count=gtld_count,
        gtld_brand_count=gtld_brand_count,
        gtld_non_brand_count=gtld_non_brand_count,
        cctld_linked=cctld_linked,
        gtld_linked=gtld_linked,
        gtld_brand_linked=gtld_brand_linked,
        gtld_non_brand_linked=gtld_non_brand_linked,
    )
