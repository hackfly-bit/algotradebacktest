from django import template

register = template.Library()


@register.filter
def pct(value):
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "—"
