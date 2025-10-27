# Demo Project

This demo project showcases the ``air_quality`` app in a runnable Django project. The
app can ingest data from the public [OpenAQ](https://openaq.org/) API and expose it via
the demo site's views.

## Synchronising air quality data

Run the ``sync_air_quality`` management command to load or refresh monitoring metadata
and recent measurements:

```bash
python manage.py sync_air_quality
```

The command performs two steps:

1. Fetch regions and monitoring sites from the ``/v3/locations`` endpoint and store the
   information in the ``Region`` and ``MonitoringSite`` models.
2. Fetch the latest measurements from the ``/v2/measurements`` endpoint. Each payload is
   normalised into ``Pollutant`` and ``Measurement`` records. Subsequent runs only
   request measurements recorded after the newest timestamp already stored locally.

A small helper script is also available for quick refreshes without passing command line
arguments:

```bash
python sync_air_quality.py
```

The script configures ``DJANGO_SETTINGS_MODULE`` automatically and dispatches to the
management command above.

## Scheduling periodic updates

For production-like scenarios you can schedule the command using cron or any other task
runner. The example below refreshes data every hour and logs output to a file inside the
project directory:

```cron
0 * * * * cd /path/to/django-ai-blocks/examples/demo_project && \
    /path/to/venv/bin/python manage.py sync_air_quality >> var/log/air_quality_sync.log 2>&1
```

When using Django's ``crontab`` or Celery integrations, simply point the job or task to
``sync_air_quality``. The command is idempotent and incremental, so running it frequently
only pulls measurements that were added since the last execution.
