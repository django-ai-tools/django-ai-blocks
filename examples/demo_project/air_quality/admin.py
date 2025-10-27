"""Admin registrations for the air quality demo app."""
from __future__ import annotations

from django.contrib import admin

from . import models


@admin.register(models.Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "external_id")
    search_fields = ("name", "external_id")


@admin.register(models.MonitoringSite)
class MonitoringSiteAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "external_id")
    list_filter = ("region",)
    search_fields = ("name", "external_id", "location_description")
    autocomplete_fields = ("region",)


@admin.register(models.Pollutant)
class PollutantAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "external_id")
    search_fields = ("name", "external_id")


@admin.register(models.Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ("site", "pollutant", "value", "measured_at", "external_id")
    list_filter = ("pollutant", "site__region")
    search_fields = ("external_id",)
    autocomplete_fields = ("site", "pollutant")
    date_hierarchy = "measured_at"


@admin.register(models.SiteAlertRule)
class SiteAlertRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "site",
        "pollutant",
        "threshold_value",
        "comparison",
        "is_active",
        "external_id",
    )
    list_filter = ("is_active", "comparison", "pollutant", "site__region")
    search_fields = ("name", "external_id")
    autocomplete_fields = ("site", "pollutant")
