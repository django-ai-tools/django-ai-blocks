from decimal import Decimal
from datetime import timedelta

import django
from django.test import TestCase
from django.utils import timezone

django.setup()

from ..models import (
    Measurement,
    MonitoringSite,
    Pollutant,
    Region,
    SiteAlert,
    SiteAlertRule,
)
from ..services import SiteAlertEvaluationService, ensure_demo_alert_rules


class SiteAlertRuleLogicTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Test Region", external_id="region-1")
        self.site = MonitoringSite.objects.create(
            region=self.region,
            name="Station 1",
            external_id="site-1",
        )
        self.pollutant = Pollutant.objects.create(
            name="PM2.5",
            external_id="pm25",
            unit="µg/m³",
        )

    def test_rule_threshold_comparisons(self):
        rule_above = SiteAlertRule.objects.create(
            site=self.site,
            pollutant=self.pollutant,
            name="Above Threshold",
            external_id="rule-above",
            threshold_value=Decimal("10.000"),
            comparison=SiteAlertRule.ABOVE,
        )
        self.assertTrue(rule_above.is_triggered(Decimal("15")))
        self.assertFalse(rule_above.is_triggered(Decimal("5")))

        rule_below = SiteAlertRule.objects.create(
            site=self.site,
            pollutant=self.pollutant,
            name="Below Threshold",
            external_id="rule-below",
            threshold_value=Decimal("20.000"),
            comparison=SiteAlertRule.BELOW,
        )
        self.assertTrue(rule_below.is_triggered(Decimal("10")))
        self.assertFalse(rule_below.is_triggered(Decimal("25")))

    def test_service_creates_and_updates_alert(self):
        measurement = Measurement.objects.create(
            site=self.site,
            pollutant=self.pollutant,
            measured_at=timezone.now(),
            value=Decimal("42.000"),
            external_id="measurement-1",
        )
        rule = SiteAlertRule.objects.create(
            site=self.site,
            pollutant=self.pollutant,
            name="High PM",
            external_id="rule-high",
            threshold_value=Decimal("30.000"),
            comparison=SiteAlertRule.ABOVE,
        )
        service = SiteAlertEvaluationService(reference_time=timezone.now())
        result = service.evaluate_measurement(measurement)
        self.assertEqual(len(result.alerts), 1)
        alert = result.alerts[0]
        self.assertEqual(alert.rule, rule)
        self.assertEqual(alert.workflow_state.name, SiteAlert.STATE_ACTIVE)

        # re-evaluating should update the same alert rather than duplicating
        measurement.value = Decimal("55.000")
        measurement.save(update_fields=["value"])
        service.evaluate_measurement(measurement)
        alert.refresh_from_db()
        self.assertEqual(alert.value, Decimal("55.000"))

    def test_ensure_demo_alert_rules(self):
        Measurement.objects.create(
            site=self.site,
            pollutant=self.pollutant,
            measured_at=timezone.now() - timedelta(hours=1),
            value=Decimal("25.000"),
            external_id="measurement-2",
        )
        created = ensure_demo_alert_rules(max_rules=2)
        self.assertGreaterEqual(created, 1)
        self.assertTrue(
            SiteAlertRule.objects.filter(external_id__startswith="demo-alert").exists()
        )
