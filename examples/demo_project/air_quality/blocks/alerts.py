"""Blocks for presenting alert information."""
from __future__ import annotations

from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from django_ai_blocks.blocks.base import BaseBlock
from django_ai_blocks.workflow.apply_transition import get_allowed_transitions

from ..models import SiteAlert

ACTIVE_SITE_ALERTS_BLOCK_CODE = "air_quality__active_site_alerts"


@dataclass(slots=True)
class AlertAction:
    name: str
    label: str
    url: str


@dataclass(slots=True)
class AlertPresentation:
    alert: SiteAlert
    actions: list[AlertAction]


class ActiveSiteAlertsBlock(BaseBlock):
    """Render the currently active alerts with workflow actions."""

    template_name = "air_quality/blocks/active_site_alerts.html"

    def __init__(self):
        self.block_name = ACTIVE_SITE_ALERTS_BLOCK_CODE
        self._content_type: ContentType | None = None

    def get_config(self, request, instance_id=None):
        return {
            "block_name": self.block_name,
        }

    def get_data(self, request, instance_id=None):
        alerts: list[AlertPresentation] = []
        queryset = (
            SiteAlert.objects.active()
            .select_related(
                "rule",
                "rule__site",
                "rule__pollutant",
                "measurement",
                "workflow_state",
            )
            .order_by("-triggered_at")
        )
        ct = self._get_content_type()
        for alert in queryset:
            transitions = get_allowed_transitions(alert, request.user)
            actions: list[AlertAction] = []
            for transition in transitions:
                actions.append(
                    AlertAction(
                        name=transition.name,
                        label=transition.name.replace("_", " ").title(),
                        url=reverse(
                            "workflow:workflow_perform_transition",
                            args=[
                                ct.app_label,
                                ct.model,
                                alert.pk,
                                transition.name,
                            ],
                        ),
                    )
                )
            alerts.append(AlertPresentation(alert=alert, actions=actions))
        return {
            "alerts": alerts,
        }

    def _get_content_type(self) -> ContentType:
        if self._content_type is None:
            self._content_type = ContentType.objects.get_for_model(SiteAlert)
        return self._content_type


__all__ = [
    "ActiveSiteAlertsBlock",
    "ACTIVE_SITE_ALERTS_BLOCK_CODE",
]
