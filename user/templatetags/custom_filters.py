from django import template
from user.models import Cliente
from user.permissions import can_edit_apontamento, can_delete_apontamento, can_view_apontamento

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
def contrast_color(hex_color):
    """Return 'white' or 'black' for best contrast on given hex color."""
    if not hex_color:
        return 'black'
    hex_color = hex_color.lstrip('#')
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        # Calculate luminance
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return 'white' if luminance < 0.5 else 'black'
    except (ValueError, IndexError):
        return 'black'


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


@register.filter
def cliente_display(value):
    """Retorna 'Corporação - Planta' dado um ID de Cliente."""
    if not value:
        return ''
    try:
        cliente = Cliente.objects.get(pk=value)
        return f"{cliente.corporation} - {cliente.plant}"
    except (Cliente.DoesNotExist, ValueError, TypeError):
        return str(value)


@register.simple_tag
def can_edit_apontamento_tag(user, apontamento):
    """Check if user can edit apontamento."""
    return can_edit_apontamento(user, apontamento)


@register.simple_tag
def can_delete_apontamento_tag(user, apontamento):
    """Check if user can delete apontamento."""
    return can_delete_apontamento(user, apontamento)


@register.simple_tag
def can_view_apontamento_tag(user, apontamento):
    """Check if user can view apontamento."""
    return can_view_apontamento(user, apontamento)
