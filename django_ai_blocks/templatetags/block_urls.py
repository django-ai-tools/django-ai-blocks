from django import template
from django.urls import NoReverseMatch, reverse


register = template.Library()


@register.simple_tag
def block_url(view_name, *args, **kwargs):
    """Reverse a block URL with graceful namespace fallback.

    Integrators might include ``django_ai_blocks.blocks.urls`` either with or
    without the ``"blocks"`` namespace.  The built-in ``url`` template tag
    raises ``NoReverseMatch`` when the chosen namespace does not exist which
    breaks block rendering.  This helper attempts to reverse using the provided
    view name first and, if that fails, retries with the ``blocks`` namespace.

    Parameters mirror :func:`django.urls.reverse`.  ``view_name`` can be either
    a fully-qualified name (e.g. ``"blocks:render_table_block"``) or an
    un-namespaced name (e.g. ``"render_table_block"``).
    """

    candidates = [view_name]
    if ":" not in view_name:
        candidates.append(f"blocks:{view_name}")

    last_error = None
    for candidate in candidates:
        try:
            return reverse(candidate, args=args, kwargs=kwargs)
        except NoReverseMatch as exc:  # pragma: no cover - intentionally retried
            last_error = exc

    if last_error is not None:
        raise last_error

    # In practice we should never reach this branch, but Django expects a
    # string return value.  Raise an explicit error if something unexpected
    # happens.
    raise NoReverseMatch(f"Unable to reverse URL for '{view_name}'")
