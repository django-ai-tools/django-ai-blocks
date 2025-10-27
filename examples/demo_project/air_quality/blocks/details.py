"""Detail-style blocks for drill-down experiences."""
from __future__ import annotations

from collections import OrderedDict

from django_ai_blocks.blocks.base import BaseBlock

from ..models import Measurement, MonitoringSite

MONITORING_SITE_DETAIL_BLOCK_CODE = "air_quality__monitoring_site_detail"


class MonitoringSiteDetailBlock(BaseBlock):
    """Show a concise overview for a single monitoring site."""

    template_name = "air_quality/blocks/monitoring_site_detail.html"

    def __init__(self):
        self.block_name = MONITORING_SITE_DETAIL_BLOCK_CODE

    def _site_query_param(self, instance_id: str | None) -> str:
        if instance_id:
            return f"{self.block_name}__{instance_id}__site"
        return f"{self.block_name}__site"

    def _get_site_choices(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        for site in MonitoringSite.objects.select_related("region").order_by(
            "region__name", "name"
        ):
            region_name = site.region.name if site.region_id else "Unknown"
            options.append((str(site.pk), f"{site.name} — {region_name}"))
        return options

    def _resolve_site(self, request, instance_id: str | None) -> MonitoringSite | None:
        param_name = self._site_query_param(instance_id)
        candidate = request.GET.get(param_name) or request.GET.get("site")
        if candidate:
            try:
                return MonitoringSite.objects.select_related("region").get(pk=int(candidate))
            except (MonitoringSite.DoesNotExist, TypeError, ValueError):
                return None
        return MonitoringSite.objects.select_related("region").order_by("name").first()

    def get_config(self, request, instance_id=None):
        selected_site = self._resolve_site(request, instance_id)
        return {
            "block_name": self.block_name,
            "site_query_param": self._site_query_param(instance_id),
            "site_options": self._get_site_choices(),
            "selected_site_id": selected_site.pk if selected_site else None,
        }

    def get_data(self, request, instance_id=None):
        site = self._resolve_site(request, instance_id)
        if not site:
            return {
                "selected_site": None,
                "latest_measurements": [],
                "latest_by_pollutant": [],
            }

        latest_measurements = list(
            Measurement.objects.filter(site=site)
            .select_related("pollutant")
            .order_by("-measured_at")[:10]
        )

        latest_by_pollutant: "OrderedDict[int, Measurement]" = OrderedDict()
        for measurement in (
            Measurement.objects.filter(site=site)
            .select_related("pollutant")
            .order_by("pollutant_id", "-measured_at")
        ):
            if measurement.pollutant_id not in latest_by_pollutant:
                latest_by_pollutant[measurement.pollutant_id] = measurement
        pollutant_snapshots = list(latest_by_pollutant.values())

        return {
            "selected_site": site,
            "latest_measurements": latest_measurements,
            "latest_by_pollutant": pollutant_snapshots[:8],
        }
