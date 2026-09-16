from __future__ import annotations

from collections import OrderedDict
from datetime import date
from typing import Any

from django.db.models import Q, QuerySet, Sum, F, ExpressionWrapper, DurationField
from django.contrib.auth import get_user_model

from user.models import ApontamentoTempo, Apontamento, PerfilUsuario, Equipe, Status, Prioridade
from user.permissions import filter_apontamentostempo_queryset, filter_apontamentos_queryset, is_admin, is_gestor, is_lider, get_user_perfil

User = get_user_model()


def get_apontamentos_base_qs() -> QuerySet:
    return ApontamentoTempo.objects.select_related(
        'apontamento', 'apontamento__cliente', 'responsavel',
        'apontamento__status', 'apontamento__prioridade', 'apontamento__equipe'
    ).filter(apontamento__isnull=False).filter(apontamento__pk__isnull=False)


def apply_permission_filter(qs: QuerySet, perfil: PerfilUsuario | None) -> QuerySet:
    if not perfil or not perfil.ativo:
        return qs.none()
    
    user = perfil.user
    return filter_apontamentostempo_queryset(user, qs)


def apply_dashboard_filters(
    qs: QuerySet,
    *,
    time_id: str | None = None,
    usuario_id: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    status: str | None = None,
    prioridade: str | None = None,
    perfil: PerfilUsuario | None = None
) -> QuerySet:
    if time_id and perfil and perfil.is_gestor_or_above():
        equipe = Equipe.objects.filter(pk=time_id, ativo=True).first()
        if equipe:
            qs = qs.filter(apontamento__equipe=equipe)
        else:
            return qs.none()

    if usuario_id:
        qs = qs.filter(responsavel_id=usuario_id)

    if data_inicio:
        qs = qs.filter(data__gte=data_inicio)
    if data_fim:
        qs = qs.filter(data__lte=data_fim)

    if status:
        qs = qs.filter(apontamento__status_id=status)
    if prioridade:
        qs = qs.filter(apontamento__prioridade_id=prioridade)

    return qs


def get_default_date_range() -> tuple[str, str]:
    today = date.today()
    start = f"{today.year}-{today.month:02d}-01"
    if today.month == 12:
        end = f"{today.year + 1}-01-01"
    else:
        end = f"{today.year}-{today.month + 1:02d}-01"
    return start, end


def get_dashboard_queryset(request, perfil: PerfilUsuario | None) -> QuerySet:
    """
    Returns queryset for dashboard - shows current month by default, 
    most recent first (-data, -hora_inicial).
    For admin/gestor: show their own first, then others.
    """
    qs = get_apontamentos_base_qs()
    qs = apply_permission_filter(qs, perfil)

    # Default: show current month
    data_inicio, data_fim = get_default_date_range()
    month_qs = qs.filter(data__gte=data_inicio, data__lte=data_fim)
    
    # If month is sparse but we have historical data, show latest 10 globally
    if month_qs.count() < 10 and qs.count() >= 10:
        qs = month_qs | qs.filter(data__lt=data_inicio)  # union with older data
    else:
        qs = month_qs

    # For admin/gestor: order by own first, then most recent
    if perfil and perfil.is_gestor_or_above():
        user = perfil.user
        from django.db.models import Case, When, Value, BooleanField
        qs = qs.annotate(
            is_own=Case(
                When(responsavel=user, then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        ).order_by('-is_own', '-data', '-hora_inicial')
    else:
        # Always order by most recent first
        qs = qs.order_by('-data', '-hora_inicial')
    
    return qs


def calculate_kpis(qs: QuerySet) -> dict[str, Any]:
    today = date.today()
    total_hoje = qs.filter(data=today).count()

    # Get Apontamento queryset for correct time aggregation (using tempo_investido_minutos)
    from user.models import Apontamento
    ap_qs = Apontamento.objects.filter(
        id__in=qs.values_list('apontamento_id', flat=True)
    )
    total_minutos = ap_qs.aggregate(total=Sum('tempo_investido_minutos'))['total'] or 0
    horas_str = f"{total_minutos // 60}h {total_minutos % 60}m"

    em_aberto = qs.filter(apontamento__status__status__iexact='aberto').count()

    # Case-insensitive match for CONCLUIDO/CONCLUÍDO variations
    concluidos = qs.filter(
        Q(apontamento__status__status__iexact='concluido') | 
        Q(apontamento__status__status__iexact='concluído')
    ).count()
    total_status = qs.exclude(apontamento__status__status__iexact='cancelado').count()
    sla_pct = round((concluidos / total_status * 100), 1) if total_status > 0 else 0

    return {
        'total_hoje': total_hoje,
        'horas_trabalhadas': horas_str,
        'em_aberto': em_aberto,
        'sla_pct': sla_pct,
    }


def get_daily_compliance(qs: QuerySet) -> list[dict]:
    """
    Returns compliance per day for current month.
    """
    today = date.today()
    data_inicio, data_fim = get_default_date_range()
    
    month_qs = qs.filter(data__gte=data_inicio, data__lte=data_fim)
    
    from django.db.models import Count
    daily = month_qs.values('data').annotate(
        total=Count('id'),
        concluidos=Count('id', filter=Q(apontamento__status__status__iexact='concluido') | Q(apontamento__status__status__iexact='concluído'))
    ).order_by('data')
    
    result = []
    for d in daily:
        total = d['total']
        concluidos = d['concluidos']
        pct = round((concluidos / total * 100), 1) if total > 0 else 0
        result.append({
            'data': d['data'],
            'total': total,
            'concluidos': concluidos,
            'pct': pct,
        })
    return result


def agrupar_por_data(qs: QuerySet, current_user=None) -> tuple[OrderedDict, dict]:
    """
    Group ApontamentoTempo entries by date, but sum using Apontamento.tempo_investido_minutos
    for consistency with edit form.
    """
    from user.models import Apontamento
    
    apontamentos_tempo = list(qs)

    # Get unique apontamento IDs from this queryset
    apontamento_ids = {ap_tempo.apontamento_id for ap_tempo in apontamentos_tempo}
    
    # Fetch Apontamento objects with tempo_investido_minutos
    ap_qs = Apontamento.objects.filter(id__in=apontamento_ids).select_related('status', 'prioridade')
    
    # Build a map of apontamento_id -> Apontamento object
    ap_map = {ap.id: ap for ap in ap_qs}
    
    agrupados = OrderedDict()
    totais = {}

    for ap_tempo in apontamentos_tempo:
        ap = ap_map.get(ap_tempo.apontamento_id)
        if not ap:
            continue
        data = ap_tempo.data
        agrupados.setdefault(data, []).append(ap_tempo)

    for data, lista in agrupados.items():
        total = 0
        for ap_tempo in lista:
            ap = ap_map.get(ap_tempo.apontamento_id)
            if ap and ap.tempo_investido_minutos is not None:
                total += ap.tempo_investido_minutos
            elif ap_tempo.tempo_investido_minutos is not None:
                total += ap_tempo.tempo_investido_minutos
            else:
                total += ap_tempo.tempo_calculado_minutos
        totais[data] = total

    return agrupados, totais


def get_filter_options(request, perfil: PerfilUsuario | None) -> dict:
    """
    Returns filter options for dashboard - teams, users, etc.
    """
    from user.models import Equipe, User
    
    options = {}
    
    if perfil and perfil.is_gestor_or_above():
        options['times'] = list(Equipe.objects.filter(ativo=True).values('pk', 'nome'))
        
        time_id = request.GET.get('time', '')
        if time_id:
            options['usuarios'] = list(User.objects.filter(
                perfil__ativo=True, perfil__equipe_id=time_id
            ).values('pk', 'first_name', 'last_name', 'username'))
        else:
            options['usuarios'] = list(User.objects.filter(
                perfil__ativo=True
            ).values('pk', 'first_name', 'last_name', 'username'))
    elif perfil and perfil.is_lider_or_above():
        options['usuarios'] = list(perfil.get_visible_users().values(
            'pk', 'first_name', 'last_name', 'username'
        ))
    
    return options