"""Database models for the air quality demo app."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db import models

from django_ai_blocks.workflow.models import Workflow, State
from django_ai_blocks.workflow.models.workflow_model_mixin import WorkflowModelMixin


class SiteAlertRuleQuerySet(models.QuerySet):
    """Custom queryset helpers for alert rule lookups."""

    def active(self):
        """Return only alert rules that are currently enabled."""

        return self.filter(is_active=True)

    def for_measurement(self, measurement: "Measurement") -> "SiteAlertRuleQuerySet":
        """Filter rules applicable to the given measurement."""

        return self.filter(site=measurement.site, pollutant=measurement.pollutant)


class SiteAlertQuerySet(models.QuerySet):
    """Queryset helpers for site alerts."""

    def active(self):
        """Return alerts that are still in the active workflow state."""

        return self.filter(
            workflow_state__name=SiteAlert.STATE_ACTIVE
        )


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

    objects: SiteAlertRuleQuerySet = SiteAlertRuleQuerySet.as_manager()

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

    def is_triggered(self, value: Decimal | float | int | None) -> bool:
        """Determine whether ``value`` breaches the configured threshold."""

        if value is None:
            return False
        candidate = Decimal(str(value))
        if self.comparison == self.ABOVE:
            return candidate >= self.threshold_value
        return candidate <= self.threshold_value

    def applicable_measurements(self, measurements: Iterable["Measurement"]):
        """Yield measurements that belong to the configured site/pollutant."""

        for measurement in measurements:
            if (
                measurement.site_id == self.site_id
                and measurement.pollutant_id == self.pollutant_id
            ):
                yield measurement

    def matches_measurement(self, measurement: "Measurement") -> bool:
        """Return True when ``measurement`` references the same site & pollutant."""

        return (
            measurement.site_id == self.site_id
            and measurement.pollutant_id == self.pollutant_id
        )


class SiteAlert(WorkflowModelMixin):
    """An alert instance representing a rule breach."""

    STATE_ACTIVE = "Active"
    STATE_ACKNOWLEDGED = "Acknowledged"
    STATE_MUTED = "Muted"

    DEFAULT_WORKFLOW_NAME = "Air Quality Alert Lifecycle"

    rule = models.ForeignKey(
        SiteAlertRule,
        on_delete=models.CASCADE,
        related_name="alerts",
        verbose_name="alert rule",
    )
    measurement = models.ForeignKey(
        "Measurement",
        on_delete=models.CASCADE,
        related_name="alerts",
        verbose_name="measurement",
    )
    triggered_at = models.DateTimeField(db_index=True, verbose_name="triggered at")
    value = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        verbose_name="measurement value",
    )
    note = models.TextField(blank=True, verbose_name="note")

    objects: SiteAlertQuerySet = SiteAlertQuerySet.as_manager()

    class Meta:
        ordering = ("-triggered_at", "-pk")
        verbose_name = "Site alert"
        verbose_name_plural = "Site alerts"
        constraints = [
            models.UniqueConstraint(
                fields=("rule", "measurement"),
                name="unique_alert_per_rule_measurement",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Alert for {self.rule} at {self.triggered_at:%Y-%m-%d %H:%M}"

    @property
    def status_label(self) -> str:
        return self.workflow_state.name if self.workflow_state_id else ""

    @classmethod
    def get_default_workflow(cls) -> Workflow:
        """Return the workflow governing site alerts, creating a stub if missing."""

        workflow = Workflow.objects.filter(name=cls.DEFAULT_WORKFLOW_NAME).first()
        if workflow is None:
            ct = ContentType.objects.get_for_model(cls)
            workflow, _ = Workflow.objects.get_or_create(
                name=cls.DEFAULT_WORKFLOW_NAME,
                defaults={"content_type": ct},
            )
        elif workflow.content_type_id is None:
            workflow.content_type = ContentType.objects.get_for_model(cls)
            workflow.save(update_fields=["content_type"])
        return workflow

    @classmethod
    def get_active_state(cls) -> State | None:
        workflow = cls.get_default_workflow()
        return workflow.states.filter(name=cls.STATE_ACTIVE).first()

    def mark_active(self) -> None:
        """Ensure the instance is attached to the default workflow in the active state."""

        workflow = self.get_default_workflow()
        self.workflow = workflow
        if not self.workflow_state_id:
            active_state = self.get_active_state()
            if active_state is None:
                active_state = workflow.states.filter(is_start=True).first()
            if active_state:
                self.workflow_state = active_state
