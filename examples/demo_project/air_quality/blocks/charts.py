"""Chart blocks highlighting air quality trends."""
from __future__ import annotations

from collections import defaultdict
from datetime import date as date_cls, timedelta
from typing import Iterable

import plotly.graph_objects as go
from django.db.models import Avg
from django.db.models.functions import TruncDate
from django.utils import timezone

from django_ai_blocks.blocks.block_types.chart.chart_block import ChartBlock

from ..models import Measurement, Pollutant, Region

POLLUTANT_TREND_BLOCK_CODE = "air_quality__pollutant_trend"


def _parse_iso_date(value):
    if not value:
        return None
    if isinstance(value, date_cls):
        return value
    try:
        return date_cls.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


class PollutantTrendChartBlock(ChartBlock):
    """Render pollutant readings as a time-series line chart."""

    def __init__(self):
        super().__init__(
            POLLUTANT_TREND_BLOCK_CODE,
            default_layout={
                "height": 420,
                "margin": {"l": 55, "r": 30, "t": 40, "b": 45},
                "legend": {"orientation": "h", "yanchor": "bottom", "y": -0.2},
            },
        )

    def get_filter_schema(self, request):
        def _pollutant_choices(user):
            return [
                (str(p.pk), p.name)
                for p in Pollutant.objects.order_by("name").only("id", "name")
            ]

        def _region_choices(user):
            return [
                (str(region.pk), region.name)
                for region in Region.objects.order_by("name").only("id", "name")
            ]

        def _site_choices(user):
            from ..models import MonitoringSite

            return [
                (str(site.pk), site.name)
                for site in MonitoringSite.objects.order_by("name").only("id", "name")[:200]
            ]

        return {
            "pollutant": {
                "type": "select",
                "label": "Pollutant",
                "choices": _pollutant_choices,
            },
            "region": {
                "type": "select",
                "label": "Region",
                "choices": _region_choices,
            },
            "site": {
                "type": "multiselect",
                "label": "Monitoring Site",
                "multiple": True,
                "choices": _site_choices,
            },
            "date_from": {"type": "date", "label": "Start Date"},
            "date_to": {"type": "date", "label": "End Date"},
        }

    def _ensure_pollutant(self, filters) -> Pollutant | None:
        pollutant_id = filters.get("pollutant")
        pollutant = None
        if pollutant_id:
            try:
                pollutant = Pollutant.objects.get(pk=int(pollutant_id))
            except (Pollutant.DoesNotExist, TypeError, ValueError):
                pollutant = None
        if not pollutant:
            pollutant = Pollutant.objects.order_by("name").first()
        return pollutant

    def get_figure(self, user, filters):
        pollutant = self._ensure_pollutant(filters)
        if not pollutant:
            fig = go.Figure()
            fig.update_layout(title="No pollutant data available")
            return fig

        qs = Measurement.objects.filter(pollutant=pollutant).select_related(
            "site", "site__region"
        )

        region_id = filters.get("region")
        if region_id:
            try:
                qs = qs.filter(site__region_id=int(region_id))
            except (TypeError, ValueError):
                pass

        site_filter = filters.get("site")
        if site_filter:
            if not isinstance(site_filter, (list, tuple)):
                site_filter = [site_filter]
            site_ids = []
            for value in site_filter:
                try:
                    site_ids.append(int(value))
                except (TypeError, ValueError):
                    continue
            if site_ids:
                qs = qs.filter(site_id__in=site_ids)

        date_from = _parse_iso_date(filters.get("date_from"))
        date_to = _parse_iso_date(filters.get("date_to"))
        if not date_from and not date_to:
            date_to = timezone.now().date()
            date_from = date_to - timedelta(days=30)
        if date_from:
            qs = qs.filter(measured_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(measured_at__date__lte=date_to)

        qs = self.filter_queryset(user, qs)

        daily_series = (
            qs.annotate(day=TruncDate("measured_at"))
            .values("day", "site__name")
            .annotate(avg_value=Avg("value"))
            .order_by("site__name", "day")
        )

        traces: dict[str, dict[str, list]] = defaultdict(lambda: {"x": [], "y": []})
        for entry in daily_series:
            site_name = entry["site__name"] or "Unknown site"
            traces[site_name]["x"].append(entry["day"])
            traces[site_name]["y"].append(float(entry["avg_value"] or 0))

        if not traces:
            fig = go.Figure()
            fig.update_layout(title=f"No readings for {pollutant.name}")
            return fig

        fig = go.Figure()
        for site_name, payload in traces.items():
            fig.add_trace(
                go.Scatter(
                    x=payload["x"],
                    y=payload["y"],
                    mode="lines+markers",
                    name=site_name,
                )
            )

        fig.update_layout(
            title=f"{pollutant.name} Trend",
            xaxis_title="Date",
            yaxis_title=f"{pollutant.unit} average",
            hovermode="x unified",
        )
        return fig
