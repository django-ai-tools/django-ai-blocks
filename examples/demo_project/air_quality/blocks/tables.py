"""Table block implementations for the air quality demo."""
from __future__ import annotations

from datetime import date as date_cls, timedelta

from django.db.models import Count, Max, Q
from django.utils import timezone

from django_ai_blocks.blocks.block_types.table.table_block import TableBlock

from ..models import Measurement, MonitoringSite, Region

MONITORING_SITE_DIRECTORY_BLOCK_CODE = "air_quality__monitoring_site_directory"
LATEST_MEASUREMENTS_BLOCK_CODE = "air_quality__latest_measurements"


def _parse_iso_date(value):
    """Parse ISO formatted dates coming from filter inputs."""

    if not value:
        return None
    if isinstance(value, date_cls):
        return value
    try:
        return date_cls.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


class _DefaultColumnConfigMixin:
    """Provide sensible defaults when no column configuration exists."""

    def get_default_columns(self) -> list[dict[str, str]]:
        raise NotImplementedError

    def get_default_field_names(self) -> list[str]:
        return [col["field"] for col in self.get_default_columns()]

    def _select_configs(self, request, instance_id=None):
        column_configs, filter_configs, active_column_config, active_filter_config, selected_fields = super()._select_configs(  # type: ignore[call-arg]
            request, instance_id
        )
        if not selected_fields:
            selected_fields = self.get_default_field_names()
        return (
            column_configs,
            filter_configs,
            active_column_config,
            active_filter_config,
            selected_fields,
        )

    def get_column_defs(self, user, column_config=None):
        if column_config and column_config.fields:
            return super().get_column_defs(user, column_config)
        return self.get_default_columns()


class MonitoringSiteDirectoryBlock(_DefaultColumnConfigMixin, TableBlock):
    """Display monitoring sites with quick access to recent activity metrics."""

    def __init__(self):
        super().__init__(MONITORING_SITE_DIRECTORY_BLOCK_CODE)

    def get_model(self):
        return MonitoringSite

    def get_default_columns(self) -> list[dict[str, str]]:
        return [
            {"field": "name", "title": "Site"},
            {"field": "region__name", "title": "Region"},
            {"field": "location_description", "title": "Location"},
            {"field": "pollutant_count", "title": "Pollutants"},
            {"field": "measurement_count", "title": "Measurements (7d)"},
            {"field": "latest_measurement_at", "title": "Last Measurement"},
        ]

    def get_filter_schema(self, request):
        def _region_choices(user):
            return [
                (str(region.pk), region.name)
                for region in Region.objects.order_by("name").only("id", "name")
            ]

        return {
            "region": {
                "type": "multiselect",
                "label": "Region",
                "multiple": True,
                "choices": _region_choices,
            },
            "search": {
                "type": "text",
                "label": "Search",
                "placeholder": "Name or description",
            },
            "has_recent": {
                "type": "boolean",
                "label": "Has data in last 7 days",
            },
        }

    def get_queryset(self, user, filters, active_column_config):
        recent_cutoff = timezone.now() - timedelta(days=7)
        qs = (
            MonitoringSite.objects.select_related("region")
            .annotate(
                pollutant_count=Count("measurements__pollutant", distinct=True),
                measurement_count=Count(
                    "measurements",
                    filter=Q(measurements__measured_at__gte=recent_cutoff),
                    distinct=True,
                ),
                latest_measurement_at=Max("measurements__measured_at"),
            )
            .order_by("region__name", "name")
        )

        region_filter = filters.get("region")
        if region_filter:
            if not isinstance(region_filter, (list, tuple)):
                region_filter = [region_filter]
            region_ids = []
            for value in region_filter:
                try:
                    region_ids.append(int(value))
                except (TypeError, ValueError):
                    continue
            if region_ids:
                qs = qs.filter(region_id__in=region_ids)

        search = (filters.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(location_description__icontains=search)
                | Q(region__name__icontains=search)
            )

        has_recent = filters.get("has_recent")
        if has_recent:
            qs = qs.filter(latest_measurement_at__gte=recent_cutoff)

        return qs

    def get_tabulator_options_overrides(self, user):
        return {"paginationSize": 15}


class LatestMeasurementsTableBlock(_DefaultColumnConfigMixin, TableBlock):
    """Show the most recent measurements for quick triage and export."""

    def __init__(self):
        super().__init__(LATEST_MEASUREMENTS_BLOCK_CODE)

    def get_model(self):
        return Measurement

    def get_default_columns(self) -> list[dict[str, str]]:
        return [
            {"field": "measured_at", "title": "Timestamp"},
            {"field": "site__region__name", "title": "Region"},
            {"field": "site__name", "title": "Site"},
            {"field": "pollutant__name", "title": "Pollutant"},
            {"field": "value", "title": "Value"},
            {"field": "pollutant__unit", "title": "Unit"},
        ]

    def get_filter_schema(self, request):
        def _pollutant_choices(user):
            from ..models import Pollutant

            return [
                (str(pollutant.pk), pollutant.name)
                for pollutant in Pollutant.objects.order_by("name").only("id", "name")
            ]

        def _region_choices(user):
            return [
                (str(region.pk), region.name)
                for region in Region.objects.order_by("name").only("id", "name")
            ]

        def _site_choices(user):
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
            "date_from": {
                "type": "date",
                "label": "Recorded From",
            },
            "date_to": {
                "type": "date",
                "label": "Recorded To",
            },
        }

    def get_queryset(self, user, filters, active_column_config):
        qs = (
            Measurement.objects.select_related("site", "site__region", "pollutant")
            .order_by("-measured_at")
        )

        pollutant_id = filters.get("pollutant")
        if pollutant_id:
            try:
                qs = qs.filter(pollutant_id=int(pollutant_id))
            except (TypeError, ValueError):
                pass

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
        if date_from:
            qs = qs.filter(measured_at__date__gte=date_from)

        date_to = _parse_iso_date(filters.get("date_to"))
        if date_to:
            qs = qs.filter(measured_at__date__lte=date_to)

        return qs[:250]

    def get_tabulator_options_overrides(self, user):
        return {"paginationSize": 25, "paginationSizeSelector": [25, 50, 100]}
