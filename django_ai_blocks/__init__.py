"""Public exports for the Django AI Blocks application."""

from .apps import DjangoAIBlocksConfig
from .conf import settings

__all__ = ["settings", "DjangoAIBlocksConfig"]

# Django < 3.2 compatibility
default_app_config = "django_ai_blocks.apps.DjangoAIBlocksConfig"
