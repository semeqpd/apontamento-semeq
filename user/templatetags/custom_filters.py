from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, '-')


@register.filter
def duration_minutes(duration):
    """Convert DurationField to total minutes."""
    if duration is None:
        return 0
    total_seconds = duration.total_seconds()
    return int(total_seconds / 60)


@register.filter
def format_hhmm(minutes):
    """Format total minutes as 'Xh Ymin' (e.g. 135 -> '2h 15min')."""
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return '0min'
    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f'{hours}h {mins}min'
    if hours:
        return f'{hours}h'
    return f'{mins}min'
