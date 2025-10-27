"""Helpers for seeding demo layouts that showcase the air quality blocks."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction

from django_ai_blocks.blocks.models.block import Block
from django_ai_blocks.layout.models import Layout, LayoutBlock

from .tables import (
    LATEST_MEASUREMENTS_BLOCK_CODE,
    MONITORING_SITE_DIRECTORY_BLOCK_CODE,
)
from .details import MONITORING_SITE_DETAIL_BLOCK_CODE
from .charts import POLLUTANT_TREND_BLOCK_CODE

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LayoutBlockSpec:
    code: str
    x: int
    y: int
    w: int
    h: int
    title: str
    note: str = ""
    preferred_filter_name: str = ""
    preferred_column_config_name: str = ""


class AirQualityDashboardLayout:
    """Seed a curated layout that highlights drill-down workflows."""

    name = "Air Quality Monitoring"
    description = (
        "Interactive dashboard combining regional filters, station directories, "
        "and pollutant trends to explore live air quality readings."
    )
    category = "Air Quality"

    block_specs: tuple[LayoutBlockSpec, ...] = (
        LayoutBlockSpec(
            code=MONITORING_SITE_DIRECTORY_BLOCK_CODE,
            x=0,
            y=0,
            w=6,
            h=5,
            title="Monitoring Sites",
        ),
        LayoutBlockSpec(
            code=MONITORING_SITE_DETAIL_BLOCK_CODE,
            x=6,
            y=0,
            w=6,
            h=4,
            title="Selected Site Detail",
            note="Choose a site from the directory to view recent readings.",
        ),
        LayoutBlockSpec(
            code=LATEST_MEASUREMENTS_BLOCK_CODE,
            x=0,
            y=5,
            w=6,
            h=5,
            title="Latest Measurements",
        ),
        LayoutBlockSpec(
            code=POLLUTANT_TREND_BLOCK_CODE,
            x=6,
            y=4,
            w=6,
            h=6,
            title="Pollutant Trend",
            note="Compare pollutant behaviour across regions or individual sites.",
        ),
    )

    def __init__(self, user):
        self.user = user
        self.layout: Layout | None = None

    def ensure(self) -> Layout:
        with transaction.atomic():
            layout, _ = Layout.objects.get_or_create(
                user=self.user,
                name=self.name,
                defaults={
                    "visibility": Layout.VISIBILITY_PRIVATE,
                    "description": self.description,
                    "category": self.category,
                },
            )
            desired_codes = {spec.code for spec in self.block_specs}
            existing = {
                lb.block.code: lb
                for lb in layout.blocks.select_related("block").all()
            }

            for position, spec in enumerate(self.block_specs):
                block = Block.objects.filter(code=spec.code).first()
                if not block:
                    LOGGER.debug("Skipping layout block for unknown code %s", spec.code)
                    continue
                defaults = {
                    "position": position,
                    "x": spec.x,
                    "y": spec.y,
                    "w": spec.w,
                    "h": spec.h,
                    "title": spec.title,
                    "note": spec.note,
                    "preferred_filter_name": spec.preferred_filter_name,
                    "preferred_column_config_name": spec.preferred_column_config_name,
                }
                instance = existing.get(spec.code)
                if instance:
                    updated = False
                    for field, value in defaults.items():
                        if getattr(instance, field) != value:
                            setattr(instance, field, value)
                            updated = True
                    if updated:
                        instance.save()
                else:
                    LayoutBlock.objects.create(
                        layout=layout,
                        block=block,
                        **defaults,
                    )
            layout.blocks.exclude(block__code__in=desired_codes).delete()
            self.layout = layout
        return layout


def ensure_default_air_quality_layout():
    """Create a sample layout for the first available superuser."""

    UserModel = get_user_model()
    user = (
        UserModel.objects.filter(is_superuser=True)
        .order_by("pk")
        .first()
    )
    if not user:
        LOGGER.debug("No superuser available to seed the demo air quality layout")
        return None

    builder = AirQualityDashboardLayout(user=user)
    return builder.ensure()


__all__ = [
    "AirQualityDashboardLayout",
    "ensure_default_air_quality_layout",
]
