#!/usr/bin/env python
"""Convenience script to trigger the air quality synchronization command."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    """Run the sync_air_quality management command within the demo project."""
    project_root = Path(__file__).resolve().parent
    repo_root = project_root.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo_project.settings")

    from django.core.management import call_command

    call_command("sync_air_quality")


if __name__ == "__main__":
    main()
