"""Admin registrations for the ``django_ai_blocks`` app.

This module ensures that all admin registrations defined in the nested
packages are imported when Django's admin autodiscovery runs.
"""

from importlib import import_module

for module_path in (
    "django_ai_blocks.blocks.admin",
    "django_ai_blocks.layout.admin",
    "django_ai_blocks.workflow.admin",
):
    import_module(module_path)
