from django.apps import AppConfig


class AirQualityConfig(AppConfig):
    """Application configuration for the air quality demo app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "examples.demo_project.air_quality"
    verbose_name = "Air Quality"
