"""Domain services for the air quality demo."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

from django.db import transaction
from django.utils import timezone

from .models import Measurement, SiteAlert, SiteAlertRule

DEMO_ALERT_EXTERNAL_PREFIX = "demo-alert"


@dataclass(slots=True)
class EvaluationResult:
    """Container summarising evaluation output for a measurement."""

    measurement: Measurement
    alerts: Sequence[SiteAlert]


class SiteAlertEvaluationService:
    """Evaluate measurements against configured site alert rules."""

    def __init__(self, *, reference_time=None):
        self.reference_time = reference_time or timezone.now()

    def evaluate_measurement(self, measurement: Measurement) -> EvaluationResult:
        """Evaluate a single measurement and create/update alerts."""

        triggered: list[SiteAlert] = []
        applicable_rules = SiteAlertRule.objects.active().for_measurement(measurement)
        for rule in applicable_rules:
            if not rule.is_triggered(measurement.value):
                continue
            alert = self._upsert_alert(rule, measurement)
            triggered.append(alert)
        return EvaluationResult(measurement=measurement, alerts=tuple(triggered))

    def evaluate_recent_measurements(
        self, *, window: timedelta = timedelta(hours=6)
    ) -> list[EvaluationResult]:
        """Evaluate measurements recorded within ``window`` of reference time."""

        since = self.reference_time - window
        results: list[EvaluationResult] = []
        queryset = (
            Measurement.objects.filter(measured_at__gte=since)
            .select_related("site", "pollutant")
            .order_by("-measured_at")
        )
        for measurement in queryset.iterator():
            result = self.evaluate_measurement(measurement)
            if result.alerts:
                results.append(result)
        return results

    @transaction.atomic
    def _upsert_alert(self, rule: SiteAlertRule, measurement: Measurement) -> SiteAlert:
        """Create or refresh an alert for ``rule`` triggered by ``measurement``."""

        workflow = SiteAlert.get_default_workflow()
        alert = (
            SiteAlert.objects.active()
            .filter(rule=rule)
            .select_for_update(skip_locked=True)
            .first()
        )
        if alert:
            alert.measurement = measurement
            alert.triggered_at = measurement.measured_at
            alert.value = measurement.value
            alert.mark_active()
            alert.save(update_fields=["measurement", "triggered_at", "value", "workflow", "workflow_state"])
            return alert

        alert, _ = SiteAlert.objects.get_or_create(
            rule=rule,
            measurement=measurement,
            defaults={
                "triggered_at": measurement.measured_at,
                "value": measurement.value,
                "workflow": workflow,
            },
        )
        if alert.workflow_id is None:
            alert.workflow = workflow
        alert.mark_active()
        alert.save()
        return alert


def ensure_demo_alert_rules(max_rules: int = 5) -> int:
    """Create a handful of engaging demo alert rules if none exist."""

    existing = SiteAlertRule.objects.filter(external_id__startswith=DEMO_ALERT_EXTERNAL_PREFIX)
    if existing.count() >= max_rules:
        return 0

    created = 0
    seen_pairs: set[tuple[int, int]] = {
        (rule.site_id, rule.pollutant_id) for rule in existing
    }

    measurements = (
        Measurement.objects.select_related("site", "pollutant")
        .order_by("-measured_at")
        .iterator()
    )

    for measurement in measurements:
        pair = (measurement.site_id, measurement.pollutant_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        rule_name = f"{measurement.site.name} {measurement.pollutant.name} alert"
        external_id = f"{DEMO_ALERT_EXTERNAL_PREFIX}|{measurement.site_id}|{measurement.pollutant_id}"
        threshold = (Decimal(str(measurement.value)) * Decimal("0.9")).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )
        rule, created_flag = SiteAlertRule.objects.get_or_create(
            site=measurement.site,
            pollutant=measurement.pollutant,
            name=rule_name,
            defaults={
                "external_id": external_id,
                "threshold_value": threshold,
                "comparison": SiteAlertRule.ABOVE,
                "is_active": True,
            },
        )
        if created_flag:
            created += 1
        if created >= max_rules:
            break

    return created


__all__ = [
    "SiteAlertEvaluationService",
    "EvaluationResult",
    "ensure_demo_alert_rules",
]
