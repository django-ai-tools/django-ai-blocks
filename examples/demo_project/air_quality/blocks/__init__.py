"""Block implementations for the air quality demo."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Iterable

from django.db import IntegrityError
from django.db.models.signals import post_migrate
from django.db.utils import OperationalError, ProgrammingError

from django_ai_blocks.blocks.registry import BlockRegistry
from django_ai_blocks.blocks.services.seeding import create_or_update_blocks

from .alerts import (
    ACTIVE_SITE_ALERTS_BLOCK_CODE,
    ActiveSiteAlertsBlock,
)
from .charts import (
    POLLUTANT_TREND_BLOCK_CODE,
    PollutantTrendChartBlock,
)
from .details import (
    MONITORING_SITE_DETAIL_BLOCK_CODE,
    MonitoringSiteDetailBlock,
)
from .tables import (
    LATEST_MEASUREMENTS_BLOCK_CODE,
    LatestMeasurementsTableBlock,
    MONITORING_SITE_DIRECTORY_BLOCK_CODE,
    MonitoringSiteDirectoryBlock,
)
from ..services import SiteAlertEvaluationService, ensure_demo_alert_rules
from .layouts import ensure_default_air_quality_layout

LOGGER = logging.getLogger(__name__)


BLOCK_DEFINITIONS: Iterable[dict[str, str]] = (
    {
        "code": ACTIVE_SITE_ALERTS_BLOCK_CODE,
        "name": "Active Site Alerts",
        "description": (
            "Live list of triggered alert rules with acknowledge and mute "
            "actions to demonstrate workflow permissions."
        ),
    },
    {
        "code": MONITORING_SITE_DIRECTORY_BLOCK_CODE,
        "name": "Monitoring Site Directory",
        "description": (
            "Directory of monitoring stations with regional context and recent "
            "activity summaries."
        ),
    },
    {
        "code": LATEST_MEASUREMENTS_BLOCK_CODE,
        "name": "Latest Air Quality Measurements",
        "description": (
            "Stream of the newest pollutant readings across the monitored "
            "network with drill-down filters."
        ),
    },
    {
        "code": MONITORING_SITE_DETAIL_BLOCK_CODE,
        "name": "Monitoring Site Detail",
        "description": (
            "Focused view of a single monitoring station including location "
            "metadata and most recent readings."
        ),
    },
    {
        "code": POLLUTANT_TREND_BLOCK_CODE,
        "name": "Pollutant Trend",
        "description": (
            "Interactive time-series visualisation showing pollutant trends "
            "for selected regions or sites."
        ),
    },
)

# Module-level singletons so repeated registrations reuse the same instances.
SITE_DIRECTORY_BLOCK = MonitoringSiteDirectoryBlock()
MEASUREMENT_TABLE_BLOCK = LatestMeasurementsTableBlock()
SITE_DETAIL_BLOCK = MonitoringSiteDetailBlock()
POLLUTANT_TREND_BLOCK = PollutantTrendChartBlock()
ACTIVE_ALERTS_BLOCK = ActiveSiteAlertsBlock()


def register_air_quality_blocks(registry: BlockRegistry) -> None:
    """Register demo air quality blocks with the global registry."""

    for code, block in (
        (ACTIVE_SITE_ALERTS_BLOCK_CODE, ACTIVE_ALERTS_BLOCK),
        (MONITORING_SITE_DIRECTORY_BLOCK_CODE, SITE_DIRECTORY_BLOCK),
        (LATEST_MEASUREMENTS_BLOCK_CODE, MEASUREMENT_TABLE_BLOCK),
        (MONITORING_SITE_DETAIL_BLOCK_CODE, SITE_DETAIL_BLOCK),
        (POLLUTANT_TREND_BLOCK_CODE, POLLUTANT_TREND_BLOCK),
    ):
        try:
            registry.register(code, block)
        except ValueError:
            LOGGER.debug("Block %s already registered; skipping", code)

    def _post_migrate_callback(**kwargs):
        try:
            create_or_update_blocks(BLOCK_DEFINITIONS)
        except (OperationalError, ProgrammingError, IntegrityError) as exc:
            LOGGER.debug(
                "Skipping block seeding until migrations complete: %s", exc
            )
        except Exception:  # pragma: no cover - defensive guard
            LOGGER.exception("Failed seeding air quality blocks")

        try:
            ensure_default_air_quality_layout()
        except (OperationalError, ProgrammingError, IntegrityError) as exc:
            LOGGER.debug(
                "Deferring demo layout creation until database is ready: %s", exc
            )
        except Exception:  # pragma: no cover - defensive guard
            LOGGER.exception("Failed to ensure air quality demo layout")

        try:
            created = ensure_demo_alert_rules()
            if created:
                SiteAlertEvaluationService().evaluate_recent_measurements(
                    window=timedelta(days=1)
                )
        except (OperationalError, ProgrammingError, IntegrityError) as exc:
            LOGGER.debug("Alert seeding deferred until database ready: %s", exc)
        except Exception:  # pragma: no cover - defensive guard
            LOGGER.exception("Failed ensuring demo alert rules")

    post_migrate.connect(
        _post_migrate_callback,
        dispatch_uid="air_quality_demo_layout_seed",
        weak=False,
    )


__all__ = [
    "register_air_quality_blocks",
    "SITE_DIRECTORY_BLOCK",
    "MEASUREMENT_TABLE_BLOCK",
    "SITE_DETAIL_BLOCK",
    "POLLUTANT_TREND_BLOCK",
    "ACTIVE_ALERTS_BLOCK",
]
