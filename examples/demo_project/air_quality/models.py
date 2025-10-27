"""Database models for the air quality demo app."""
from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models


class Region(models.Model):
    """Geographic grouping for monitoring sites."""

    name = models.CharField(max_length=255, verbose_name="name")
    external_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="external ID",
        help_text="Identifier from the upstream data source.",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Region"
        verbose_name_plural = "Regions"

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.name


class MonitoringSite(models.Model):
    """Specific monitoring locations that collect measurement data."""

    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name="sites",
        verbose_name="region",
    )
    name = models.CharField(max_length=255, verbose_name="name")
    external_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="external ID",
        help_text="Identifier from the upstream data source.",
    )
    location_description = models.TextField(
        blank=True,
        verbose_name="location description",
        help_text="Optional human readable description of the site's location.",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Monitoring site"
        verbose_name_plural = "Monitoring sites"

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.name


class Pollutant(models.Model):
    """Pollutant that can be measured at a monitoring site."""

    name = models.CharField(max_length=255, verbose_name="name")
    external_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="external ID",
        help_text="Identifier from the upstream data source.",
    )
    unit = models.CharField(
        max_length=32,
        verbose_name="measurement unit",
        help_text="Typical unit, e.g. µg/m³ or ppm.",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Pollutant"
        verbose_name_plural = "Pollutants"

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.name


class Measurement(models.Model):
    """Individual measurement recorded for a pollutant at a site."""

    site = models.ForeignKey(
        MonitoringSite,
        on_delete=models.CASCADE,
        related_name="measurements",
        verbose_name="monitoring site",
    )
    pollutant = models.ForeignKey(
        Pollutant,
        on_delete=models.CASCADE,
        related_name="measurements",
        verbose_name="pollutant",
    )
    measured_at = models.DateTimeField(
        db_index=True,
        verbose_name="measured at",
        help_text="Timestamp provided by the upstream data source.",
    )
    value = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        verbose_name="value",
        help_text="Numeric value recorded for the pollutant.",
    )
    external_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="external ID",
        help_text="Identifier from the upstream data source.",
    )

    class Meta:
        ordering = ("-measured_at",)
        verbose_name = "Measurement"
        verbose_name_plural = "Measurements"
        constraints = [
            models.UniqueConstraint(
                fields=("site", "pollutant", "measured_at"),
                name="unique_measurement_per_site_pollutant_timestamp",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.pollutant} at {self.site} on {self.measured_at:%Y-%m-%d %H:%M}"


class SiteAlertRule(models.Model):
    """Optional alert threshold configured for a site/pollutant combination."""

    ABOVE = "above"
    BELOW = "below"
    COMPARISON_CHOICES = (
        (ABOVE, "Above or equal to threshold"),
        (BELOW, "Below or equal to threshold"),
    )

    site = models.ForeignKey(
        MonitoringSite,
        on_delete=models.CASCADE,
        related_name="alert_rules",
        verbose_name="monitoring site",
    )
    pollutant = models.ForeignKey(
        Pollutant,
        on_delete=models.CASCADE,
        related_name="alert_rules",
        verbose_name="pollutant",
    )
    name = models.CharField(max_length=255, verbose_name="name")
    external_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="external ID",
        help_text="Identifier from the upstream data source.",
    )
    threshold_value = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        verbose_name="threshold value",
    )
    comparison = models.CharField(
        max_length=8,
        choices=COMPARISON_CHOICES,
        default=ABOVE,
        verbose_name="comparison",
    )
    is_active = models.BooleanField(default=True, verbose_name="is active")

    class Meta:
        ordering = ("name",)
        verbose_name = "Site alert rule"
        verbose_name_plural = "Site alert rules"
        constraints = [
            models.UniqueConstraint(
                fields=("site", "pollutant", "name"),
                name="unique_alert_rule_per_site_pollutant_name",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.name} ({self.site} - {self.pollutant})"
