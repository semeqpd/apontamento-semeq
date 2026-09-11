from __future__ import annotations

from collections import OrderedDict
from typing import Any

from django.db.models import Q, QuerySet, Sum, F, ExpressionWrapper, DurationField
from django.contrib.auth import get_user_model

from user.models import Apontamento, ApontamentoTempo, PerfilUsuario, Equipe, Status, Prioridade, Atividade, TipoProblema
from user.permissions import filter_apontamentostempo_queryset, filter_apontamentos_queryset, is_admin, is_gestor, is_lider, get_user_perfil

User = get_user_model()


def get_apontamentos_list_qs(request, perfil: PerfilUsuario | None) -> QuerySet:
    """
    Retorna queryset de ApontamentoTempo para a lista principal.
    
    Ordered by most recent first (-data, -hora_inicial).
    Excludes 'concluido' status by default unless explicitly filtered.
    """
    qs = ApontamentoTempo.objects.select_related(
        'apontamento', 'apontamento__cliente', 'responsavel',
        'apontamento__status', 'apontamento__prioridade', 'apontamento__equipe'
    ).filter(apontamento__isnull=False).filter(apontamento__pk__isnull=False)

    qs = apply_permission_filter(qs, perfil)

    # Busca por ticket (exclusiva)
    ticket = request.GET.get('ticket', '').strip() or request.GET.get('q', '').strip()
    if ticket:
        qs = qs.filter(apontamento__ticket__icontains=ticket)

    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(apontamento__status__status=status)
    # No default status exclusion - show all statuses (like Dashboard)

    prioridade = request.GET.get('prioridade', '').strip()
    if prioridade:
        qs = qs.filter(apontamento__prioridade__nome=prioridade)

    # Filtros de data opcionais
    data_inicio = request.GET.get('data_inicio', '').strip()
    if data_inicio:
        qs = qs.filter(data__gte=data_inicio)

    data_fim = request.GET.get('data_fim', '').strip()
    if data_fim:
        qs = qs.filter(data__lte=data_fim)

    equipe_id = request.GET.get('time', '').strip()
    if equipe_id and perfil and perfil.is_gestor_or_above():
        qs = qs.filter(apontamento__equipe_id=equipe_id)

    usuario_id = request.GET.get('usuario', '').strip()
    if usuario_id:
        if perfil and perfil.is_gestor_or_above():
            qs = qs.filter(responsavel_id=usuario_id)
        elif perfil and perfil.is_lider_or_above():
            qs = qs.filter(responsavel_id=usuario_id, apontamento__equipe=perfil.equipe)
        else:
            qs = qs.filter(responsavel_id=usuario_id, responsavel=request.user)

    # Most recent first
    return qs.order_by('-data', '-hora_inicial')


def apply_permission_filter(qs: QuerySet, perfil: PerfilUsuario | None) -> QuerySet:
    if not perfil or not perfil.ativo:
        return qs.none()
    
    # Use the centralized permission function
    # We need a user object, create a mock or get from perfil
    user = perfil.user
    return filter_apontamentostempo_queryset(user, qs)


def get_list_context_data(request, perfil: PerfilUsuario | None, qs: QuerySet) -> dict[str, Any]:
    context = {'perfil': perfil}

    context['status_choices'] = [(s.pk, s.status) for s in Status.objects.filter(ativo=True).order_by('ordem', 'status')]
    context['lista_status'] = list(Status.objects.filter(ativo=True).order_by('ordem', 'status'))
    context['prioridade_choices'] = [(p.pk, p.nome) for p in Prioridade.objects.filter(ativo=True).order_by('ordem', 'nome')]
    context['equipe_choices'] = [(e.pk, e.nome) for e in Equipe.objects.filter(ativo=True).order_by('ordem', 'nome')]
    context['atividade_choices'] = [(a.pk, a.nome) for a in Atividade.objects.filter(ativo=True).order_by('ordem', 'nome')]
    context['tipoproblema_choices'] = [(t.pk, t.nome) for t in TipoProblema.objects.filter(ativo=True).order_by('ordem', 'nome')]

    # Filtro de equipe selecionada (para encadeamento Equipe -> Responsável)
    equipe_filter = request.GET.get('equipe', '')

    # Responsáveis para o filtro - usuários ativos com perfil ativo
    # Se equipe_filter estiver presente, filtra apenas membros daquela equipe
    responsaveis_qs = User.objects.filter(
        is_active=True, perfil__ativo=True
    ).select_related('perfil', 'perfil__equipe').order_by('first_name', 'username')

    if equipe_filter:
        responsaveis_qs = responsaveis_qs.filter(perfil__equipe_id=equipe_filter)

    context['responsavel_choices'] = responsaveis_qs

    # Use 'ticket' as the parameter name for the search input
    context['ticket_filter'] = request.GET.get('ticket', '') or request.GET.get('q', '')
    context['status_filter'] = request.GET.get('status', '')
    context['prioridade_filter'] = request.GET.get('prioridade', '')
    context['data_inicio'] = request.GET.get('data_inicio', '')
    context['data_fim'] = request.GET.get('data_fim', '')
    context['equipe_filter'] = equipe_filter
    context['time_filter'] = request.GET.get('time', '')
    context['responsavel_filter'] = request.GET.get('responsavel', '')

    if perfil and perfil.is_gestor_or_above():
        context['times'] = Equipe.objects.filter(ativo=True)
        time_filter = request.GET.get('time', '')
        if time_filter:
            context['usuarios'] = User.objects.filter(
                perfil__ativo=True, perfil__equipe_id=time_filter
            ).select_related('perfil')
        else:
            context['usuarios'] = User.objects.filter(perfil__ativo=True).select_related('perfil')
        context['usuario_filter'] = request.GET.get('usuario', '')
    elif perfil and perfil.is_lider_or_above():
        context['usuarios'] = perfil.get_visible_users()
        context['usuario_filter'] = request.GET.get('usuario', '')

    return context


def agrupar_por_data(qs: QuerySet) -> tuple[OrderedDict, dict]:
    """
    Group ApontamentoTempo entries by date, but sum using Apontamento.tempo_investido_minutos
    for consistency with edit form.
    """
    from user.models import Apontamento
    
    # Get unique apontamento IDs from this queryset
    apontamento_ids = list(qs.values_list('apontamento_id', flat=True).distinct())
    
    # Fetch Apontamento objects with tempo_investido_minutos
    ap_qs = Apontamento.objects.filter(id__in=apontamento_ids)
    
    # Build a map of apontamento_id -> Apontamento object
    ap_map = {ap.id: ap for ap in ap_qs}
    
    agrupados = OrderedDict()
    totais = {}

    for ap_tempo in qs:
        ap = ap_map.get(ap_tempo.apontamento_id)
        if not ap:
            continue
        data = ap_tempo.data
        agrupados.setdefault(data, []).append(ap_tempo)

    for data, lista in agrupados.items():
        total = 0
        for ap_tempo in lista:
            ap = ap_map.get(ap_tempo.apontamento_id)
            if ap and ap.tempo_investido_minutos:
                total += ap.tempo_investido_minutos
            elif ap_tempo.tempo_investido_minutos:
                total += ap_tempo.tempo_investido_minutos
            else:
                total += ap_tempo.tempo_calculado_minutos
        totais[data] = total

    return agrupados, totais


def get_export_queryset(perfil: PerfilUsuario | None, user) -> QuerySet:
    qs = ApontamentoTempo.objects.select_related(
        'apontamento', 'apontamento__cliente', 'responsavel',
        'apontamento__status', 'apontamento__prioridade', 'apontamento__equipe',
        'apontamento__atividade', 'apontamento__tipo_problema'
    ).filter(apontamento__isnull=False).filter(apontamento__pk__isnull=False)

    if perfil and perfil.ativo:
        return filter_apontamentostempo_queryset(user, qs)
    return qs.none()


# =====================================================================
# ATENDIMENTO SELECTORS
# =====================================================================

def get_atendimentos_list_qs(request, perfil: PerfilUsuario | None) -> QuerySet:
    qs = Atendimento.objects.select_related(
        'cliente', 'responsavel', 'equipe', 'status', 'prioridade', 'projeto', 'atividade'
    ).all()

    qs = apply_atendimento_permission_filter(qs, perfil)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(ticket__icontains=q) |
            Q(cliente__corporation__icontains=q) |
            Q(projeto__nome__icontains=q) |
            Q(solicitante__nome__icontains=q) |
            Q(responsavel__first_name__icontains=q) |
            Q(responsavel__last_name__icontains=q)
        )

    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status__status=status)

    prioridade = request.GET.get('prioridade', '').strip()
    if prioridade:
        qs = qs.filter(prioridade__nome=prioridade)

    equipe_id = request.GET.get('time', '').strip()
    if equipe_id:
        qs = qs.filter(equipe_id=equipe_id)

    responsavel_id = request.GET.get('responsavel', '').strip()
    if responsavel_id:
        qs = qs.filter(responsavel_id=responsavel_id)

    data_inicial = request.GET.get('data_inicial', '').strip()
    if data_inicial:
        qs = qs.filter(data_inicial__gte=data_inicial)

    data_final = request.GET.get('data_fim', '').strip()
    if data_final:
        qs = qs.filter(data_inicial__lte=data_final)

    return qs.order_by('-criado_em')


def apply_atendimento_permission_filter(qs: QuerySet, perfil: PerfilUsuario | None) -> QuerySet:
    if not perfil or not perfil.ativo:
        return qs.none()
    
    user = perfil.user
    return filter_apontamentos_queryset(user, qs)


def get_apontamento_context_data(request, perfil: PerfilUsuario | None, qs: QuerySet) -> dict[str, Any]:
    context = {'perfil': perfil}

    context['status_choices'] = [(s.pk, s.status) for s in Status.objects.filter(ativo=True).order_by('ordem', 'status')]
    context['prioridade_choices'] = [(p.pk, p.nome) for p in Prioridade.objects.filter(ativo=True).order_by('ordem', 'nome')]
    context['equipe_choices'] = [(e.pk, e.nome) for e in Equipe.objects.filter(ativo=True).order_by('ordem', 'nome')]
    context['responsavel_choices'] = User.objects.filter(perfil__ativo=True).select_related('perfil')

    context['search'] = request.GET.get('q', '')
    context['status_filter'] = request.GET.get('status', '')
    context['prioridade_filter'] = request.GET.get('prioridade', '')
    context['time_filter'] = request.GET.get('time', '')
    context['responsavel_filter'] = request.GET.get('responsavel', '')
    context['data_inicial'] = request.GET.get('data_inicial', '')
    context['data_final'] = request.GET.get('data_fim', '')

    return context