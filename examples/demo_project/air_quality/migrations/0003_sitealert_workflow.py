from django.db import migrations


def seed_site_alert_workflow(apps, schema_editor):
    Workflow = apps.get_model("django_ai_blocks", "Workflow")
    State = apps.get_model("django_ai_blocks", "State")
    Transition = apps.get_model("django_ai_blocks", "Transition")
    SiteAlert = apps.get_model("air_quality", "SiteAlert")
    ContentType = apps.get_model("contenttypes", "ContentType")

    workflow_name = "Air Quality Alert Lifecycle"
    ct = ContentType.objects.get_for_model(SiteAlert)
    workflow, created = Workflow.objects.get_or_create(
        name=workflow_name,
        defaults={"content_type": ct},
    )
    if workflow.content_type_id != ct.id:
        workflow.content_type = ct
        workflow.save(update_fields=["content_type"])

    state_active, _ = State.objects.get_or_create(
        workflow=workflow,
        name="Active",
        defaults={"is_start": True},
    )
    state_ack, _ = State.objects.get_or_create(
        workflow=workflow,
        name="Acknowledged",
        defaults={"is_end": True},
    )
    state_muted, _ = State.objects.get_or_create(
        workflow=workflow,
        name="Muted",
        defaults={"is_end": True},
    )

    Transition.objects.get_or_create(
        workflow=workflow,
        source_state=state_active,
        dest_state=state_ack,
        name="acknowledge",
    )
    Transition.objects.get_or_create(
        workflow=workflow,
        source_state=state_active,
        dest_state=state_muted,
        name="mute",
    )

    SiteAlert.objects.filter(workflow__isnull=True).update(
        workflow=workflow,
        workflow_state=state_active,
    )

    from django_ai_blocks.workflow.utils import generate_workflow_permissions_for_model

    generate_workflow_permissions_for_model(SiteAlert)


def unseed_site_alert_workflow(apps, schema_editor):
    Workflow = apps.get_model("django_ai_blocks", "Workflow")
    State = apps.get_model("django_ai_blocks", "State")
    Transition = apps.get_model("django_ai_blocks", "Transition")
    workflow_name = "Air Quality Alert Lifecycle"
    workflow = Workflow.objects.filter(name=workflow_name).first()
    if workflow:
        SiteAlert.objects.filter(workflow=workflow).update(
            workflow=None,
            workflow_state=None,
        )
        Transition.objects.filter(workflow=workflow).delete()
        State.objects.filter(workflow=workflow).delete()
        workflow.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("air_quality", "0002_sitealert"),
    ]

    operations = [
        migrations.RunPython(seed_site_alert_workflow, unseed_site_alert_workflow),
    ]
