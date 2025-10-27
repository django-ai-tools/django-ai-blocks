# Vision & Overview
The "Django-AI-Blocks" App Framework is the foundation for building modular, intelligent, and reusable business interfaces.

It reimagines how Django applications present and interact with data—transforming traditional views into a composable “Block” architecture, where each block represents a functional, permission-aware UI component that can be dropped anywhere in the system.

The framework aims to become an internal low-code platform for the organization —where developers build new modules by defining models and workflows,
and the UI is generated dynamically through blocks and layouts.

Ultimately, users will design dashboards, reports, and workflows through an AI-assisted interface, bridging the gap between data, design, and decision-making.

# Core Vision
To create a configurable, workflow-aware, AI-ready UI platform where every data view—table, form, chart, Gantt, Kanban, or dashboard—is a block that can be registered, rendered, and reused across multiple domains (production, procurement, engineering, projects, etc.).
This architecture allows developers and power users to assemble applications visually, without duplicating code or violating domain boundaries.

# Architectural Pillars
**Blocks as Building Units**
Each block encapsulates its data source, permissions, display rules, and front-end template logic. Blocks can render dynamic Tables, Forms, Charts, or Gantt views with minimal configuration.

**Layouts as Composers**
Layouts (or pages) organize blocks by drag/drop mechanism. A layout is a “screen definition” built entirely by referencing reusable blocks.

**Registry-Driven Design**
Every block registers itself into a centralized registry, making it discoverable and plug-and-play. Domain apps contribute their own blocks via registration hooks.

**User Personalization**
Users can persist column configurations, filters, and view preferences through BlockColumnConfig and BlockFilterConfig, giving them a truly personalized experience.

**Integrated Governance**
The block engine integrates with the Permissions and Workflow layers—enforcing field-level visibility, edit rights, and state-based restrictions automatically.

# Long-Term Goal
To evolve the system into an AI-assisted interface builder where blocks can be discovered, combined, and configured through natural language or contextual prompts—bridging the gap between business logic and user experience.

## Installation

Follow these steps to install and configure `django-ai-blocks` within your Django project:

1. **Install the package and its dependencies** using pip, either from PyPI or a local source checkout:

   ```bash
   pip install django-ai-blocks
   # or, from a local clone
   pip install /path/to/django-ai-blocks
   ```

2. **Register the app and URLs** in your Django settings and root URLconf so Django loads the app configuration and workflow routes:

   ```python
   INSTALLED_APPS = [
       # …
       "django_ai_blocks",
   ]

   urlpatterns = [
       # …
       path("workflow/", include("django_ai_blocks.workflow.urls", namespace="workflow")),
   ]
   ```

3. **Enable the permissions middleware (recommended)** to clear per-request permission caches used by the workflow layer:

   ```python
   MIDDLEWARE = [
       # …
       "django_ai_blocks.permissions.middleware.PermissionCacheMiddleware",
   ]
   ```

4. **Apply database migrations** so the Block, Layout, Workflow, and related tables are created:

   ```bash
   python manage.py migrate
   ```

5. **Adjust optional configuration** as needed, such as `PERMISSIONS_STAFF_BYPASS`, fiscal year start, or custom block registrars, via standard Django settings overrides. The app will automatically load additional registrars listed under the `BLOCKS` setting during initialization.

## Demo project

A minimal Django project is provided under `examples/demo_project/` to make it easy to explore the library from a local checkout.

1. **Install dependencies in editable mode** so the demo project uses the local source tree:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Run migrations and start the server** using the project's manage script:

   ```bash
   python examples/demo_project/manage.py migrate
   python examples/demo_project/manage.py runserver
   ```

3. **Access the admin** at <http://127.0.0.1:8000/admin/>. Create a superuser with `python examples/demo_project/manage.py createsuperuser` if needed.
