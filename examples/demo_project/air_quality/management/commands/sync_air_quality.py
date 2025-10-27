"""Synchronize air quality reference data and measurements from OpenAQ."""
from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Dict, Tuple

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from air_quality.models import Measurement, MonitoringSite, Pollutant, Region
from air_quality.services import SiteAlertEvaluationService, ensure_demo_alert_rules

LOGGER = logging.getLogger(__name__)

API_ROOT_V2 = "https://api.openaq.org/v2"
API_ROOT_V3 = "https://api.openaq.org/v3"
REQUEST_TIMEOUT = 30
LOCATIONS_ENDPOINT = "/locations"
MEASUREMENTS_ENDPOINT = "/measurements"
PAGE_LIMIT = 100


@dataclass
class SyncStats:
    """Basic counters for reporting progress at the end of a sync run."""

    regions: int = 0
    sites: int = 0
    pollutants: int = 0
    measurements: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "regions": self.regions,
            "sites": self.sites,
            "pollutants": self.pollutants,
            "measurements": self.measurements,
        }


class Command(BaseCommand):
    """Fetch monitoring sites and measurements from the OpenAQ API."""

    help = (
        "Fetch regions, monitoring sites, and recent measurements from the OpenAQ API "
        "and store them in the local database. Subsequent runs only request new "
        "measurements since the most recent timestamp stored locally."
    )

    def handle(self, *args, **options):
        stats = SyncStats()

        LOGGER.info("Fetching regions and monitoring sites from OpenAQ")
        regions_by_key, sites_by_external_id, region_updates, site_updates = self.sync_sites()
        stats.regions += region_updates
        stats.sites += site_updates

        LOGGER.info("Fetching measurements from OpenAQ")
        pollutants_created, measurements_written = self.sync_measurements(sites_by_external_id)
        stats.pollutants += pollutants_created
        stats.measurements += measurements_written

        summary = ", ".join(f"{key}={value}" for key, value in stats.as_dict().items())
        self.stdout.write(self.style.SUCCESS(f"Air quality sync completed: {summary}"))

    def sync_sites(self) -> Tuple[Dict[str, Region], Dict[str, MonitoringSite], int, int]:
        """Fetch regions and monitoring sites from the v3 locations endpoint."""

        regions_by_key: Dict[str, Region] = {}
        sites_by_external_id: Dict[str, MonitoringSite] = {}
        regions_created_or_updated = 0
        sites_created_or_updated = 0

        for payload in self._fetch_paginated(f"{API_ROOT_V3}{LOCATIONS_ENDPOINT}"):
            location_id = payload.get("id") or payload.get("locationId")
            if location_id is None:
                LOGGER.debug("Skipping location without id: %s", payload)
                continue
            external_site_id = str(location_id)

            region_name = payload.get("city") or payload.get("country") or "Unknown"
            region_key = f"{payload.get('country', 'XX')}|{region_name}"
            region = regions_by_key.get(region_key)
            if region is None:
                region_defaults = {"name": region_name}
                region, created = Region.objects.update_or_create(
                    external_id=region_key,
                    defaults=region_defaults,
                )
                if created:
                    LOGGER.debug("Created region %s (%s)", region.name, region.external_id)
                elif region.name != region_name:
                    region.name = region_name
                    region.save(update_fields=["name"])
                    LOGGER.debug("Updated region %s (%s)", region.name, region.external_id)
                regions_by_key[region_key] = region
                regions_created_or_updated += 1
            else:
                if region.name != region_name:
                    region.name = region_name
                    region.save(update_fields=["name"])
                    LOGGER.debug("Updated region %s (%s)", region.name, region.external_id)
                    regions_created_or_updated += 1

            site_defaults = {
                "name": payload.get("name") or payload.get("location") or region_name,
                "region": region,
                "location_description": payload.get("description")
                or payload.get("address")
                or "",
            }
            site = sites_by_external_id.get(external_site_id)
            if site is None:
                site, created = MonitoringSite.objects.update_or_create(
                    external_id=external_site_id,
                    defaults=site_defaults,
                )
                if not created:
                    updates = {}
                    if site.name != site_defaults["name"]:
                        updates["name"] = site_defaults["name"]
                    if site.location_description != site_defaults["location_description"]:
                        updates["location_description"] = site_defaults["location_description"]
                    if site.region_id != region.id:
                        updates["region"] = region
                    if updates:
                        for field, value_to_set in updates.items():
                            setattr(site, field, value_to_set)
                        site.save(update_fields=list(updates.keys()))
                        LOGGER.debug(
                            "Updated monitoring site %s (%s)", site.name, site.external_id
                        )
                else:
                    LOGGER.debug(
                        "Created monitoring site %s (%s)", site.name, site.external_id
                    )
                sites_by_external_id[site.external_id] = site
                sites_created_or_updated += 1
            else:
                updates = {}
                if site.name != site_defaults["name"]:
                    updates["name"] = site_defaults["name"]
                if site.location_description != site_defaults["location_description"]:
                    updates["location_description"] = site_defaults["location_description"]
                if site.region_id != region.id:
                    updates["region"] = region
                if updates:
                    for field, value_to_set in updates.items():
                        setattr(site, field, value_to_set)
                    site.save(update_fields=list(updates.keys()))
                    LOGGER.debug(
                        "Updated monitoring site %s (%s)", site.name, site.external_id
                    )
                    sites_created_or_updated += 1

        return regions_by_key, sites_by_external_id, regions_created_or_updated, sites_created_or_updated

    def sync_measurements(self, sites: Dict[str, MonitoringSite]) -> Tuple[int, int]:
        """Fetch recent measurements for the known monitoring sites."""

        latest_measurement = Measurement.objects.order_by("-measured_at").first()
        if latest_measurement is not None:
            since = latest_measurement.measured_at
        else:
            since = timezone.now() - timedelta(days=7)

        params = {
            "order_by": "date",
            "sort": "asc",
            "limit": PAGE_LIMIT,
            "date_from": since.isoformat(),
        }

        pollutants_created = 0
        measurements_written = 0
        alert_service = SiteAlertEvaluationService()
        pollutant_cache: Dict[str, Pollutant] = {
            pollutant.external_id: pollutant
            for pollutant in Pollutant.objects.all()
        }

        with transaction.atomic():
            for payload in self._fetch_paginated(
                f"{API_ROOT_V2}{MEASUREMENTS_ENDPOINT}", params=params
            ):
                measurement_id = payload.get("id")
                location_id = payload.get("locationId")
                parameter = payload.get("parameter")
                unit = payload.get("unit")
                value = payload.get("value")
                date_info = payload.get("date", {})
                measured_at_raw = date_info.get("utc") or date_info.get("local")

                if measurement_id is None or location_id is None or parameter is None:
                    LOGGER.debug("Skipping measurement missing required keys: %s", payload)
                    continue
                if value is None:
                    LOGGER.debug("Skipping measurement without value: %s", payload)
                    continue

                measured_at = parse_datetime(str(measured_at_raw)) if measured_at_raw else None
                if measured_at is None:
                    LOGGER.debug("Skipping measurement with invalid timestamp: %s", payload)
                    continue

                site = sites.get(str(location_id))
                if site is None:
                    # Attempt lazy lookup if the site wasn't seen earlier in this run.
                    try:
                        site = MonitoringSite.objects.get(external_id=str(location_id))
                    except MonitoringSite.DoesNotExist:
                        LOGGER.debug(
                            "Skipping measurement for unknown site %s (measurement %s)",
                            location_id,
                            measurement_id,
                        )
                        continue
                    sites[str(location_id)] = site

                pollutant = pollutant_cache.get(parameter)
                pollutant_defaults = {
                    "name": parameter.replace("_", " ").title(),
                    "unit": unit or "",
                }
                if pollutant is None:
                    pollutant, created = Pollutant.objects.get_or_create(
                        external_id=parameter,
                        defaults=pollutant_defaults,
                    )
                    pollutants_created += int(created)
                    pollutant_cache[parameter] = pollutant
                else:
                    updates = {}
                    if unit and pollutant.unit != unit:
                        updates["unit"] = unit
                    if updates:
                        for field, value_to_set in updates.items():
                            setattr(pollutant, field, value_to_set)
                        pollutant.save(update_fields=list(updates.keys()))

                measurement_defaults = {
                    "site": site,
                    "pollutant": pollutant,
                    "measured_at": measured_at,
                    "value": Decimal(str(value)),
                }
                measurement, created = Measurement.objects.update_or_create(
                    external_id=str(measurement_id),
                    defaults=measurement_defaults,
                )
                if created:
                    measurements_written += 1

                alert_service.evaluate_measurement(measurement)

        if ensure_demo_alert_rules():
            alert_service.evaluate_recent_measurements(window=timedelta(days=1))

        return pollutants_created, measurements_written

    def _fetch_paginated(self, url: str, params: Dict[str, str | int] | None = None) -> Iterator[Dict]:
        """Generator that iterates through paginated OpenAQ API responses."""

        params = params.copy() if params else {}
        page = 1
        while True:
            params["page"] = page
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                raise CommandError(
                    f"Failed to fetch data from {url}: {response.status_code} {response.text}"
                )
            payload = response.json()
            results = payload.get("results", [])
            if not isinstance(results, Iterable):
                raise CommandError(f"Unexpected response payload from {url}: {payload}")

            for item in results:
                yield item

            if len(results) < int(params.get("limit", PAGE_LIMIT)):
                break

            page += 1
