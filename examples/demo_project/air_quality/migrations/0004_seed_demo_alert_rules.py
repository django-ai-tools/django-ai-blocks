from importlib import import_module

from django.db import migrations


def seed_rules(apps, schema_editor):
    services = import_module("examples.demo_project.air_quality.services")
    ensure_demo_alert_rules = getattr(services, "ensure_demo_alert_rules")
    SiteAlertEvaluationService = getattr(services, "SiteAlertEvaluationService")

    created = ensure_demo_alert_rules()
    if created:
        SiteAlertEvaluationService().evaluate_recent_measurements()


def unseed_rules(apps, schema_editor):
    SiteAlertRule = apps.get_model("air_quality", "SiteAlertRule")
    SiteAlertRule.objects.filter(external_id__startswith="demo-alert").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("air_quality", "0003_sitealert_workflow"),
    ]

    operations = [
        migrations.RunPython(seed_rules, unseed_rules),
    ]
