from __future__ import annotations

from collections import OrderedDict
from typing import Any

from django.db.models import Q, QuerySet, Sum, F, ExpressionWrapper, DurationField
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateformat import format as django_format

from user.models import Apontamento, ApontamentoTempo, PerfilUsuario, Equipe, Status, Prioridade, Atividade, TipoProblema
from user.permissions import filter_apontamentostempo_queryset, filter_apontamentos_queryset, is_admin, is_gestor, is_lider, get_user_perfil

User = get_user_model()


def format_data_portugues(data):
    """Formata data para português: 'Segunda-feira, 14/09/2026'"""
    if not data:
        return ''
    dias_semana = [
        'Segunda-feira', 'Terça-feira', 'Quarta-feira', 
        'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'
    ]
    dia_semana = dias_semana[data.weekday()]
    return f'{dia_semana}, {data.strftime("%d/%m/%Y")}'


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
        qs = qs.filter(apontamento__status_id=status)

    prioridade = request.GET.get('prioridade', '').strip()
    if prioridade:
        qs = qs.filter(apontamento__prioridade_id=prioridade)

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
    # For admin/gestor: show their own first (responsavel == user), then others
    if perfil and perfil.is_gestor_or_above():
        user = perfil.user
        # Annotate with is_own flag
        from django.db.models import Case, When, Value, BooleanField
        qs = qs.annotate(
            is_own=Case(
                When(responsavel=user, then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        ).order_by('-is_own', '-data', '-hora_inicial')
    else:
        qs = qs.order_by('-data', '-hora_inicial')
    
    return qs


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
    # Inclui usuários sem equipe (perfil__equipe__isnull=True)
    responsaveis_qs = User.objects.filter(
        is_active=True, perfil__ativo=True
    ).select_related('perfil', 'perfil__equipe').order_by('first_name', 'username')

    if equipe_filter and equipe_filter != 'sem_equipe':
        responsaveis_qs = responsaveis_qs.filter(perfil__equipe_id=equipe_filter)
    elif equipe_filter == 'sem_equipe':
        responsaveis_qs = responsaveis_qs.filter(perfil__equipe__isnull=True)

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
        # Add "Sem equipe" as first choice
        from itertools import chain
        times = list(Equipe.objects.filter(ativo=True).order_by('ordem', 'nome'))
        context['times'] = [{'id': 'sem_equipe', 'nome': 'Sem equipe'}] + [
            {'id': t.pk, 'nome': t.nome} for t in times
        ]
        time_filter = request.GET.get('time', '')
        if time_filter:
            if time_filter == 'sem_equipe':
                context['usuarios'] = User.objects.filter(
                    perfil__ativo=True, perfil__equipe__isnull=True
                ).select_related('perfil')
            else:
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
            # Use Apontamento.tempo_investido_minutos as single source of truth
            # Check explicitly for None (not falsy) because 0 is a valid value
            if ap and ap.tempo_investido_minutos is not None:
                total += ap.tempo_investido_minutos
            elif ap_tempo.tempo_investido_minutos is not None:
                total += ap_tempo.tempo_investido_minutos
            else:
                total += ap_tempo.tempo_calculado_minutos
        totais[data] = total

    return agrupados, totais


def agrupar_por_dia_equipe_usuario(qs: QuerySet) -> list:
    """
    Group ApontamentoTempo entries hierarchically: Data -> Equipe -> Usuario -> Apontamentos
    Returns a list of daily groups, each containing equipe groups, each containing usuario groups.
    """
    from user.models import Apontamento
    from collections import OrderedDict
    from django.db.models import Sum
    
    # Get unique apontamento IDs from this queryset
    apontamento_ids = list(qs.values_list('apontamento_id', flat=True).distinct())
    
    # Fetch Apontamento objects with related data
    ap_qs = Apontamento.objects.filter(id__in=apontamento_ids).select_related(
        'equipe', 'responsavel', 'responsavel__perfil', 'responsavel__perfil__equipe',
        'status', 'prioridade', 'cliente', 'projeto', 
        'atividade', 'tipo_problema', 'solicitante', 'equipamento'
    )
    
    # Build a map of apontamento_id -> Apontamento object
    ap_map = {ap.id: ap for ap in ap_qs}
    
    # Structure: {data: {equipe_id: {usuario_id: [ap_tempo, ...]}}}
    data_map = {}
    
    for ap_tempo in qs:
        ap = ap_map.get(ap_tempo.apontamento_id)
        if not ap:
            continue
        
        data = ap_tempo.data
        # Use the RESPONSAVEL'S team (perfil.equipe), not the Apontamento's equipe
        responsavel = ap.responsavel
        
        if not data:
            continue
            
        # Get the user's team from their profile
        equipe = None
        equipe_nome = "Sem Equipe"
        equipe_id = 0
        if responsavel and responsavel.perfil and responsavel.perfil.equipe:
            equipe = responsavel.perfil.equipe
            equipe_nome = equipe.nome
            equipe_id = equipe.id
        else:
            equipe_nome = "Sem Equipe"
            equipe_id = 0
        
        if not data:
            continue
            
        # Initialize nested structure
        if data not in data_map:
            data_map[data] = {}
        
        if equipe_id not in data_map[data]:
            data_map[data][equipe_id] = {
                'equipe_nome': equipe_nome,
                'equipe_id': equipe_id,
                'usuarios': {}
            }
        
        # User grouping
        if responsavel:
            user_id = responsavel.id
            user_nome = responsavel.get_full_name() or responsavel.username
        else:
            user_id = 0
            user_nome = "Sem Responsável"
            
        if user_id not in data_map[data][equipe_id]['usuarios']:
            data_map[data][equipe_id]['usuarios'][user_id] = {
                'usuario_nome': user_nome,
                'usuario_id': user_id,
                'apontamentos': []
            }
        
        data_map[data][equipe_id]['usuarios'][user_id]['apontamentos'].append(ap_tempo)
    
    # Convert to list structure for template rendering
    result = []
    
    for data, equipes in data_map.items():
        # Sort teams by name
        equipes_sorted = sorted(equipes.items(), key=lambda x: x[1]['equipe_nome'])
        
        dia = {
            'data': data,
            'data_formatada': format_data_portugues(data) if data else '',
            'equipes': []
        }
        
        for equipe_id, equipe_data in equipes_sorted:
            usuarios_sorted = sorted(
                equipe_data['usuarios'].items(), 
                key=lambda x: x[1]['usuario_nome']
            )
            
            equipe = {
                'equipe_id': equipe_id,
                'equipe_nome': equipe_data['equipe_nome'],
                'usuarios': []
            }
            
            for user_id, user_data in usuarios_sorted:
                # Calculate total minutes for this user
                total_user_minutos = 0
                for ap_tempo in user_data['apontamentos']:
                    ap = ap_map.get(ap_tempo.apontamento_id)
                    if ap and ap.tempo_investido_minutos is not None:
                        total_user_minutos += ap.tempo_investido_minutos
                    elif ap_tempo.tempo_investido_minutos is not None:
                        total_user_minutos += ap_tempo.tempo_investido_minutos
                    else:
                        total_user_minutos += ap_tempo.tempo_calculado_minutos
                
                equipe['usuarios'].append({
                    'usuario_id': user_id,
                    'usuario_nome': user_data['usuario_nome'],
                    'apontamentos': user_data['apontamentos'],
                    'total_minutos': total_user_minutos
                })
            
            dia['equipes'].append(equipe)
        
        result.append(dia)
    
    # Sort by date (most recent first)
    result.sort(key=lambda x: x['data'], reverse=True)
    
    return result


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