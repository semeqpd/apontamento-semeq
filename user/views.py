from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LogoutView, LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, DurationField
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import date, timedelta, datetime, time
from .models import Cliente, Equipamento, PerfilUsuario, Time, Apontamento, EmailVerificationToken, Status, Atividade, Prioridade, TipoProblema, Equipe, Projeto, Solicitante, ApontamentoTempo
from .forms import (
    ClienteForm, ClienteImportForm,
    UsuarioForm, ApontamentoForm, UsuarioUpdateForm,
    PublicRegistrationForm, SemeqPasswordResetForm, EquipamentoForm, EmailLoginForm, StatusForm,
    ApontamentoForm, ApontamentoTempoForm,
    AtividadeForm, PrioridadeForm, TipoProblemaForm, EquipeForm, ProjetoForm, SolicitanteForm
    )
from .throttle import rate_limit
import csv
import openpyxl
from io import BytesIO
import logging

# Logger para este módulo (usa o logger 'user' configurado em settings.py)
logger = logging.getLogger('user')
import openpyxl
from io import BytesIO
from apps.apontamentos.selectors.dashboard import (
    get_dashboard_queryset, calculate_kpis, get_daily_compliance, get_filter_options,
    agrupar_por_data
)
from apps.apontamentos.selectors.apontamentos import (
    get_apontamentos_list_qs, get_list_context_data, get_export_queryset,
    get_apontamentos_list_qs, agrupar_por_data, agrupar_por_dia_equipe_usuario
)
from apps.apontamentos.services.apontamento_service import (
    criar_apontamento, criar_apontamento_tempo, atualizar_apontamento_tempo, pode_editar,
    criar_apontamento, atualizar_apontamento, pode_editar
)
from apps.clientes.services.import_service import (
    parse_file, normalize_row, fix_encoding
)
from apps.core.views.base import (
    PermissionMixin, BaseCRUDListView, BaseCRUDCreateView,
    BaseCRUDUpdateView, BaseCRUDDeleteView
)
from .permissions import (
    can_view_apontamento, can_edit_apontamento, can_delete_apontamento,
    can_view_user, can_edit_user, can_delete_user, can_manage_users,
    filter_apontamentos_queryset, filter_apontamentostempo_queryset,
    filter_users_queryset, PermissionDenied as PermDenied
)


def HomeView(request):
    if not request.user.is_authenticated:
        return redirect('semeq:login')
    return redirect('semeq:dashboard')


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        perfil = getattr(request.user, 'perfil', None)
        qs = get_dashboard_queryset(request, perfil)
        kpis = calculate_kpis(qs)
        daily_compliance = get_daily_compliance(qs)
        
        # FORCE ordering at the very end of pipeline (most recent first)
        qs = qs.order_by('-data', '-hora_inicial')
        
        # Group by day for ALL appointments in current month
        agrupados, totais = agrupar_por_data(qs)
        
        # Status choices for dropdown
        status_choices = [(s.pk, s.status) for s in Status.objects.filter(ativo=True).order_by('ordem', 'status')]
        lista_status = list(Status.objects.filter(ativo=True).order_by('ordem', 'status'))
        
        context = {
            'perfil': perfil,
            'total_hoje': kpis['total_hoje'],
            'horas_trabalhadas': kpis['horas_trabalhadas'],
            'em_aberto': kpis['em_aberto'],
            'sla_pct': kpis['sla_pct'],
            'daily_compliance': daily_compliance,
            # Grouped by day (all days of current month)
            'apontamentos_por_data': agrupados,
            'totais_por_data': totais,
            # Status choices for dropdown
            'status_choices': status_choices,
            'lista_status': lista_status,
            # Botão Voltar - Dashboard não tem botão voltar
            'hide_back_button': True,
        }
        return render(request, 'dashboard.html', context)


# Apontamento Views
class ApontamentoListView(LoginRequiredMixin, ListView):
    model = ApontamentoTempo
    template_name = 'apontamentos/lista.html'
    context_object_name = 'apontamentos'
    paginate_by = 15

    def get_queryset(self):
        perfil = getattr(self.request.user, 'perfil', None)
        qs = get_apontamentos_list_qs(self.request, perfil)
        
        # Ensure select_related for 'apontamento' is included
        qs = qs.select_related('apontamento', 'apontamento__cliente', 'apontamento__status', 
                               'apontamento__prioridade', 'apontamento__equipe', 'responsavel')
        
        return qs

    def get_context_data(self, **kwargs):
        # Don't call super() since we're using custom queryset (ApontamentoTempo) with model=ApontamentoTempo
        # and custom context building
        from django.core.paginator import Paginator
        
        perfil = getattr(self.request.user, 'perfil', None)
        is_admin_ou_gestor = self.request.user.is_superuser or (perfil and perfil.role in ['admin', 'gestor'])
        
        # Use the FULL queryset (before pagination) for grouping
        qs = self.get_queryset()
        selector_context = get_list_context_data(self.request, perfil, qs)
        
        if is_admin_ou_gestor:
            # Admin/Gestor: Hierarchical grouping Data -> Equipe -> Usuario -> Apontamentos
            agrupamento_admin = agrupar_por_dia_equipe_usuario(qs)
            selector_context['agrupamento_admin'] = agrupamento_admin
            selector_context['is_admin_ou_gestor'] = True
        else:
            # Lider/Colaborador: Simple daily grouping with totals
            agrupados, totais = agrupar_por_data(qs)
            selector_context['apontamentos_por_data'] = agrupados
            selector_context['totais_por_data'] = totais
            selector_context['is_admin_ou_gestor'] = False
        
        # Build filter params for pagination links
        from django.http import QueryDict
        get_params = self.request.GET
        if hasattr(get_params, 'urlencode'):
            query_string = get_params.urlencode()
        else:
            query_string = '&'.join(f'{k}={v}' for k, v in get_params.items())
        filter_params = QueryDict(query_string)
        if 'page' in filter_params:
            filter_params = filter_params.copy()
            filter_params.pop('page')
        selector_context['filter_params'] = filter_params.urlencode()
        
        # Botão Voltar - Apontamentos volta para Dashboard
        selector_context['previous_page_url'] = '/dashboard/'
        selector_context['hide_back_button'] = False
        
        # Add paginator/page_obj for template compatibility
        paginator = Paginator(qs, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        selector_context['paginator'] = paginator
        selector_context['page_obj'] = page_obj
        selector_context['object_list'] = page_obj.object_list
        selector_context['is_paginated'] = page_obj.has_other_pages()
        
        return selector_context


class ApontamentoUpdateView(LoginRequiredMixin, UpdateView):
    model = Apontamento
    form_class = ApontamentoForm
    template_name = 'apontamentos/form.html'
    success_url = reverse_lazy('semeq:apontamento_lista')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not pode_editar(obj):
            messages.error(request, 'Não é possível editar um apontamento com status "Concluído".')
            return redirect('semeq:apontamento_lista')
        # Use permission function (admin/gestor can edit any, others only own)
        if not can_edit_apontamento(request.user, obj):
            messages.error(request, 'Ação não permitida. Você só pode editar os seus próprios apontamentos.')
            return redirect('semeq:apontamento_lista')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        atualizar_apontamento(self.object, **form.cleaned_data)
        messages.success(self.request, 'Apontamento atualizado com sucesso!')
        return redirect(self.get_success_url())


class ApontamentoDetailView(LoginRequiredMixin, DetailView):
    model = Apontamento
    template_name = 'apontamentos/detail.html'
    context_object_name = 'apontamento'
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'cliente', 'projeto', 'solicitante', 'equipe', 'responsavel', 
            'atividade', 'tipo_problema', 'status', 'prioridade', 'equipamento', 'criado_por'
        )
    
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not can_view_apontamento(request.user, obj):
            raise PermDenied('Você não tem permissão para visualizar este apontamento.')
        return super().dispatch(request, *args, **kwargs)


class ApontamentoStatusView(LoginRequiredMixin, View):
    @method_decorator(rate_limit(rate='30/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs) -> JsonResponse:
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Requisição inválida.'}, status=400)

        pk = kwargs.get('pk')
        ap = get_object_or_404(Apontamento, pk=pk)
        
        # Use permission function (admin/gestor can edit any, others only own)
        if not can_edit_apontamento(request.user, ap):
            return JsonResponse({'success': False, 'message': 'Ação não permitida. Você só pode alterar os seus próprios apontamentos.'}, status=403)

        # Support both form data and JSON
        import json
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                status_id = data.get('status', '').strip()
            except (json.JSONDecodeError, AttributeError):
                status_id = ''
        else:
            status_id = request.POST.get('status', '').strip()
        
        status_obj = Status.objects.filter(pk=status_id, ativo=True).first()
        if not status_obj:
            return JsonResponse({'success': False, 'message': 'Status inválido.'}, status=400)

        ap.status = status_obj
        ap.save()

        return JsonResponse({
            'success': True,
            'message': 'Status atualizado!',
            'status': ap.status.status if ap.status else '',
        })


@login_required
@require_POST
def alterar_status_apontamento(request, pk):
    """AJAX endpoint for quick status change from list/dashboard."""
    try:
        import json
        data = json.loads(request.body)
        novo_status_id = data.get('status')
        tempo_investido = data.get('tempo_investido_minutos')

        ap = get_object_or_404(Apontamento, pk=pk)

        # Use permission function (admin/gestor can edit any, others only own)
        if not can_edit_apontamento(request.user, ap):
            return JsonResponse({'success': False, 'error': 'Ação não permitida. Você só pode alterar os seus próprios apontamentos.'}, status=403)

        status_obj = Status.objects.filter(pk=novo_status_id, ativo=True).first()
        if not status_obj:
            return JsonResponse({'success': False, 'error': 'Status inválido.'}, status=400)

        # Validar se status é Concluído e requer tempo investido > 0
        if status_obj.is_concluido_fixo:
            tempo_atual = ap.tempo_investido_minutos or 0
            tempo_novo = int(tempo_investido) if tempo_investido else 0
            tempo_final = tempo_novo if tempo_novo > 0 else tempo_atual

            if tempo_final <= 0:
                return JsonResponse({
                    'success': False,
                    'requires_time': True,
                    'error': 'O tempo investido precisa ser maior que 0 para concluir.',
                    'tempo_atual': tempo_atual
                }, status=400)

            if tempo_novo > 0:
                ap.tempo_investido_minutos = tempo_novo

        ap.status = status_obj
        ap.save()

        return JsonResponse({'success': True, 'status': status_obj.status})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
def excluir_apontamento(request, pk):
    """Exclui um apontamento via POST (usado pelo modal de confirmação)."""
    apontamento = get_object_or_404(Apontamento, pk=pk)
    
    # Use permission function (admin/gestor can delete any, others only own)
    if not can_delete_apontamento(request.user, apontamento):
        raise PermissionDenied('Ação não permitida. Você só pode excluir os seus próprios apontamentos.')
    
    # Log de auditoria
    logger.info(
        f'[excluir_apontamento] EXCLUSÃO DE APONTAMENTO - '
        f'User: {request.user} (ID: {request.user.pk}), '
        f'Apontamento PK: {apontamento.pk}, '
        f'Ticket: {apontamento.ticket}, '
        f'Cliente: {apontamento.cliente}, '
        f'Responsável: {apontamento.responsavel}, '
        f'Data: {apontamento.data_inicial}, '
        f'Tempo: {apontamento.tempo_investido_minutos}min, '
        f'Status: {apontamento.status}, '
        f'Equipe: {apontamento.equipe}'
    )
    for handler in logger.handlers:
        handler.flush()
    
    apontamento.delete()
    messages.success(request, 'Apontamento excluído com sucesso!')
    return redirect('semeq:apontamento_lista')


class ApontamentoTipoProblemaView(LoginRequiredMixin, View):
    @method_decorator(rate_limit(rate='30/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs) -> JsonResponse:
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Requisição inválida.'}, status=400)

        pk = kwargs.get('pk')
        ap = get_object_or_404(Apontamento, pk=pk)
        
        # Use permission function (admin/gestor can edit any, others only own)
        if not can_edit_apontamento(request.user, ap):
            return JsonResponse({'success': False, 'message': 'Ação não permitida. Você só pode alterar os seus próprios apontamentos.'}, status=403)

        tipo_obj = TipoProblema.objects.filter(nome=request.POST.get('tipo_problema', '').strip(), ativo=True).first()
        if not tipo_obj:
            return JsonResponse({'success': False, 'message': 'Tipo de problema inválido.'}, status=400)

        ap.tipo_problema = tipo_obj
        ap.save()

        return JsonResponse({
            'success': True,
            'message': 'Tipo de problema atualizado!',
            'tipo_problema': ap.tipo_problema.nome if ap.tipo_problema else '',
        })


class ApontamentoExportView(LoginRequiredMixin, View):
    def get(self, request):
        formato = request.GET.get('formato', 'csv')
        perfil = getattr(request.user, 'perfil', None)

        qs = get_export_queryset(perfil, request.user)

        if formato == 'xlsx':
            return self.export_xlsx(qs)
        return self.export_csv(qs)

    def export_csv(self, qs):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="apontamentos_{date.today()}.csv"'
        response.write('\ufeff'.encode('utf-8'))

        writer = csv.writer(response, delimiter=';')
        writer.writerow([
            'Ticket', 'Cliente', 'Projeto', 'Solicitante', 'Equipamento',
            'Prioridade', 'Equipe', 'Responsável', 'Atividade', 'Tipo Problema',
            'Status', 'Data', 'Hora Inicial', 'Hora Final', 'Tempo (min)',
            'GW no Ar', '>18h', 'Desvio', 'Descrição'
        ])

        for a in qs:
            tempo_min = a.tempo_minutos
            if not tempo_min and a.tempo_total:
                tempo_min = int(a.tempo_total.total_seconds() / 60)
            writer.writerow([
                a.ticket, f"{a.cliente.corporation} - {a.cliente.plant}", a.projeto,
                a.solicitante, str(a.equipamento) if a.equipamento else '',
                a.prioridade.nome if a.prioridade else '',
                a.equipe.nome if a.equipe else '',
                a.responsavel.get_full_name() or a.responsavel.username,
                a.atividade.nome if a.atividade else '',
                a.tipo_problema.nome if a.tipo_problema else '',
                a.status.status if a.status else '',
                a.data.strftime('%d/%m/%Y'),
                a.hora_inicial.strftime('%H:%M') if a.hora_inicial else '',
                a.hora_final.strftime('%H:%M') if a.hora_final else '',
                tempo_min if tempo_min else '',
                'Sim' if a.gw_ar else 'Não',
                'Sim' if a.apos_18h else 'Não',
                a.get_desvio_display(), a.descricao
            ])
        return response

    def export_xlsx(self, qs):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Apontamentos'

        headers = [
            'Ticket', 'Cliente', 'Projeto', 'Solicitante', 'Equipamento',
            'Prioridade', 'Equipe', 'Responsável', 'Atividade', 'Tipo Problema',
            'Status', 'Data', 'Hora Inicial', 'Hora Final', 'Tempo (min)',
            'GW no Ar', '>18h', 'Desvio', 'Descrição'
        ]
        ws.append(headers)

        for a in qs:
            tempo_min = a.tempo_minutos
            if not tempo_min and a.tempo_total:
                tempo_min = int(a.tempo_total.total_seconds() / 60)
            ws.append([
                a.ticket, f"{a.cliente.corporation} - {a.cliente.plant}", a.projeto,
                a.solicitante, str(a.equipamento) if a.equipamento else '',
                a.prioridade.nome if a.prioridade else '',
                a.equipe.nome if a.equipe else '',
                a.responsavel.get_full_name() or a.responsavel.username,
                a.atividade.nome if a.atividade else '',
                a.tipo_problema.nome if a.tipo_problema else '',
                a.status.status if a.status else '',
                a.data.strftime('%d/%m/%Y'),
                a.hora_inicial.strftime('%H:%M') if a.hora_inicial else '',
                a.hora_final.strftime('%H:%M') if a.hora_final else '',
                tempo_min if tempo_min else '',
                'Sim' if a.gw_ar else 'Não',
                'Sim' if a.apos_18h else 'Não',
                a.get_desvio_display(), a.descricao
            ])

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="apontamentos_{date.today()}.xlsx"'
        wb.save(response)
        return response


# =====================================================================
# ATENDIMENTO & APONTAMENTO TEMPO VIEWS
# =====================================================================

class ApontamentoPermissionMixin(LoginRequiredMixin):
    """Apenas Admin e Gestor podem gerenciar apontamentos."""
    def dispatch(self, request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.is_gestor_or_above())):
            messages.error(request, 'Acesso negado. Apenas administradores e gestores.')
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)


class ApontamentoCreateView(LoginRequiredMixin, CreateView):
    model = Apontamento
    form_class = ApontamentoForm
    template_name = 'apontamentos/form.html'
    success_url = reverse_lazy('semeq:apontamento_lista')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cliente_queryset'] = Cliente.objects.all().order_by('corporation', 'plant')
        # Add data for cascading dropdowns
        context['corporacoes'] = Cliente.objects.values_list('corporation', flat=True).distinct().order_by('corporation')
        context['todos_clientes'] = Cliente.objects.filter(ativo=True).values('id', 'corporation', 'plant', 'zone')
        return context
    
    def form_valid(self, form):
        from django.db import transaction
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f'[ApontamentoCreateView] ===== INÍCIO CRIAÇÃO =====')
        logger.info(f'[ApontamentoCreateView] User: {self.request.user} (ID: {self.request.user.pk})')
        logger.info(f'[ApontamentoCreateView] User perfil: {getattr(self.request.user, "perfil", None)}')
        if hasattr(self.request.user, 'perfil') and self.request.user.perfil:
            logger.info(f'[ApontamentoCreateView] User role: {self.request.user.perfil.role}, equipe: {self.request.user.perfil.equipe}')
        logger.info(f'[ApontamentoCreateView] Form data: data_inicial={form.cleaned_data.get("data_inicial")}, tempo={form.cleaned_data.get("tempo_investido_minutos")}, responsavel={form.cleaned_data.get("responsavel")}, cliente={form.cleaned_data.get("cliente")}')
        
        form.instance.criado_por = self.request.user
        
        # Ensure responsavel is set (for non-gestor users, it's hidden and defaults to current user)
        if not form.instance.responsavel_id:
            form.instance.responsavel = self.request.user
            logger.info(f'[ApontamentoCreateView] Responsavel não definido, usando usuário atual: {self.request.user}')
        else:
            logger.info(f'[ApontamentoCreateView] Responsavel já definido: {form.instance.responsavel}')
        
        with transaction.atomic():
            # Save the Apontamento first
            response = super().form_valid(form)
            
            logger.info(f'[ApontamentoCreateView] Apontamento salvo com ID: {self.object.pk}, Data: {self.object.data_inicial}, Tempo: {self.object.tempo_investido_minutos}, Responsavel: {self.object.responsavel} (ID: {self.object.responsavel_id})')
            
            # Automatically create an ApontamentoTempo entry for the list view
            if self.object.data_inicial and self.object.tempo_investido_minutos is not None:
                total_minutes = self.object.tempo_investido_minutos
                
                # Calculate end time properly using timedelta to handle overflow
                from datetime import datetime, timedelta
                hora_inicial = time(8, 0)
                dt_inicial = datetime.combine(self.object.data_inicial, hora_inicial)
                dt_final = dt_inicial + timedelta(minutes=total_minutes)
                hora_final = dt_final.time()
                
                # If end time is next day or later, cap at 23:59
                if dt_final.date() > self.object.data_inicial:
                    hora_final = time(23, 59)
                
                try:
                    at = ApontamentoTempo.objects.create(
                        apontamento=self.object,
                        responsavel=self.object.responsavel,
                        criado_por=self.request.user,
                        data=self.object.data_inicial,
                        hora_inicial=hora_inicial,
                        hora_final=hora_final,
                        tempo_investido_minutos=total_minutes,
                        observacao='Criado automaticamente a partir do apontamento principal'
                    )
                    logger.info(f'[ApontamentoCreateView] ApontamentoTempo criado com sucesso - ID: {at.pk}')
                except Exception as e:
                    logger.exception(f'[ApontamentoCreateView] ERRO ao criar ApontamentoTempo automático: {str(e)}')
            else:
                logger.warning(f'[ApontamentoCreateView] ApontamentoTempo NÃO criado - data_inicial: {self.object.data_inicial}, tempo_investido_minutos: {self.object.tempo_investido_minutos}')
        
        messages.success(self.request, 'Apontamento criado com sucesso!')
        logger.info(f'[ApontamentoCreateView] ===== FIM CRIAÇÃO =====')
        return response


class ApontamentoUpdateView(ApontamentoPermissionMixin, UpdateView):
    model = Apontamento
    form_class = ApontamentoForm
    template_name = 'apontamentos/form.html'
    success_url = reverse_lazy('semeq:apontamento_lista')
    context_object_name = 'object'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Apontamento atualizado com sucesso!')
        return super().form_valid(form)


class ApontamentoDetailViewAdmin(ApontamentoPermissionMixin, DetailView):
    model = Apontamento
    template_name = 'apontamentos/detail.html'
    context_object_name = 'apontamento'
    
    def get_queryset(self):
        return Apontamento.objects.select_related(
            'cliente', 'responsavel', 'equipe', 'status', 'prioridade', 'projeto', 
            'atividade', 'tipo_problema', 'solicitante', 'equipamento', 'criado_por'
        ).prefetch_related('apontamentos_tempo__responsavel')


class ApontamentoTempoCreateView(LoginRequiredMixin, CreateView):
    model = ApontamentoTempo
    form_class = ApontamentoTempoForm
    template_name = 'atendimentos/apontamento_tempo_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.apontamento = get_object_or_404(Apontamento, pk=kwargs.get('apontamento_pk'))
        # REGRA ESTRITA: Apenas o próprio responsável pode adicionar tempo
        if self.apontamento.responsavel != request.user:
            messages.error(request, 'Ação não permitida. Você só pode adicionar tempo aos seus próprios apontamentos.')
            return redirect('semeq:apontamento_detalhe', pk=self.apontamento.pk)
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['apontamento'] = self.apontamento
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamento'] = self.apontamento
        return context
    
    def form_valid(self, form):
        form.instance.apontamento = self.apontamento
        form.instance.responsavel = self.apontamento.responsavel
        form.instance.criado_por = self.request.user
        messages.success(self.request, 'Apontamento de tempo adicionado com sucesso!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('semeq:apontamento_detalhe', kwargs={'pk': self.apontamento.pk})


class ApontamentoTempoUpdateView(LoginRequiredMixin, UpdateView):
    model = ApontamentoTempo
    form_class = ApontamentoTempoForm
    template_name = 'atendimentos/apontamento_tempo_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        # REGRA ESTRITA: Apenas o próprio responsável do apontamento pai pode editar
        if obj.apontamento.responsavel != request.user:
            messages.error(request, 'Ação não permitida. Você só pode editar os seus próprios apontamentos.')
            return redirect('semeq:apontamento_detalhe', pk=obj.apontamento.pk)
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['apontamento'] = self.object.apontamento
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamento'] = self.object.apontamento
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Apontamento de tempo atualizado com sucesso!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('semeq:apontamento_detalhe', kwargs={'pk': self.object.apontamento.pk})


class ApontamentoTempoDeleteView(LoginRequiredMixin, DeleteView):
    model = ApontamentoTempo
    template_name = 'atendimentos/apontamento_tempo_confirm_delete.html'
    
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        # REGRA ESTRITA: Apenas o próprio responsável do apontamento pai pode excluir
        if obj.apontamento.responsavel != request.user:
            messages.error(request, 'Ação não permitida. Você só pode excluir os seus próprios apontamentos.')
            return redirect('semeq:apontamento_detalhe', pk=obj.apontamento.pk)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamento'] = self.object.apontamento
        return context
    
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        # Log antes da exclusão
        logger.info(
            f'[ApontamentoTempoDeleteView] EXCLUSÃO DE APONTAMENTO TEMPO - '
            f'User: {request.user} (ID: {request.user.pk}), '
            f'ApontamentoTempo PK: {obj.pk}, '
            f'Apontamento: {obj.apontamento.pk} (Ticket: {obj.apontamento.ticket}), '
            f'Data: {obj.data}, '
            f'Hora Inicial: {obj.hora_inicial}, '
            f'Hora Final: {obj.hora_final}, '
            f'Tempo: {obj.tempo_investido_minutos}min, '
            f'Responsável: {obj.responsavel}'
        )
        # Force flush to ensure log is written
        for handler in logger.handlers:
            handler.flush()
        
        messages.success(request, 'Apontamento de tempo excluído com sucesso!')
        return super().delete(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse_lazy('semeq:apontamento_detalhe', kwargs={'pk': self.object.apontamento.pk})


# Cliente Views
class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clientes/lista.html'
    context_object_name = 'clientes'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.can_manage_clientes())):
            messages.error(request, 'Acesso negado. Apenas administradores e gestores.')
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        qs = Cliente.objects.all()
        
        # Text search across multiple fields
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(corporation__icontains=q) |
                Q(plant__icontains=q) 
            )
        
        # Specific field filters
        corporation = self.request.GET.get('corporation', '').strip()
        if corporation:
            qs = qs.filter(corporation__icontains=corporation)
    
        plant = self.request.GET.get('plant', '').strip()
        if plant:
            qs = qs.filter(plant__icontains=plant)

        zone = self.request.GET.get('zone', '').strip()
        if zone:
            qs = qs.filter(zone__icontains=zone)
        
        return qs.order_by('-criado_em')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pass current filter values to template
        context['filters'] = {
            'q': self.request.GET.get('q', ''),
            'corporation': self.request.GET.get('corporation', ''),
            'plant': self.request.GET.get('plant', ''),
            'zone': self.request.GET.get('zone', ''),
        }
        
        # Get distinct values for dropdowns (from base queryset without filters)
        base_qs = Cliente.objects.all()
        
        # Build filter params for pagination (exclude 'page')
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filter_params'] = params.urlencode()
        
        return context


class ClientePermissionMixin(LoginRequiredMixin):
    """Apenas Admin e Gestor podem acessar o gerenciamento de clientes."""
    def dispatch(self, request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.can_manage_clientes())):
            messages.error(request, 'Acesso negado. Apenas administradores e gestores.')
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)


class ClienteCreateView(ClientePermissionMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'cadastros/cliente_form.html'
    success_url = reverse_lazy('semeq:cadastro_clientes')
    
    def form_valid(self, form):
        messages.success(self.request, 'Cliente criado com sucesso!')
        return super().form_valid(form)


class ClienteUpdateView(ClientePermissionMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'cadastros/cliente_form.html'
    success_url = reverse_lazy('semeq:cadastro_clientes')
    
    def form_valid(self, form):
        messages.success(self.request, 'Cliente atualizado com sucesso!')
        return super().form_valid(form)


class ClienteDeleteView(ClientePermissionMixin, DeleteView):
    model = Cliente
    template_name = 'clientes/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastro_clientes')
    
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Check for related apontamentos
        self.apontamentos_count = self.object.apontamentos.count()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamentos_count'] = self.apontamentos_count
        context['is_admin'] = self.request.user.is_superuser or (
            hasattr(self.request.user, 'perfil') and self.request.user.perfil.is_admin()
        )
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Check apontamentos - auto-delete them if admin confirms
        if self.apontamentos_count > 0:
            if not (request.user.is_superuser or (
                hasattr(request.user, 'perfil') and self.request.user.perfil.is_admin()
            )):
                messages.error(request, 
                    f'Este cliente possui {self.apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir clientes com apontamentos.'
                )
                return redirect('semeq:cadastro_clientes')
            
            # Admin confirmed - delete apontamentos first
            self.object.apontamentos.all().delete()
        
        messages.success(request, 'Cliente excluído com sucesso!')
        return super().post(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Cliente excluído com sucesso!')
        return super().delete(request, *args, **kwargs)


class ClienteDeleteAllView(ClientePermissionMixin, View):
    """Delete ALL clientes + cascade (equipamentos, apontamentos). Admin only.
    Preserva o cliente padrão SEMEQ LIMEIRA."""
    
    def dispatch(self, request, *args, **kwargs):
        perfil = request.user.perfil if hasattr(request.user, 'perfil') else None
        if not (request.user.is_superuser or (perfil and perfil.is_admin())):
            messages.error(request, 'Acesso negado. Apenas administradores.')
            return redirect('semeq:cadastro_clientes')
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        from user.models import Apontamento, Equipamento, Cliente
        
        # Exclui o cliente padrão SEMEQ LIMEIRA da contagem
        clientes_count = Cliente.objects.exclude(corporation='SEMEQ', plant='LIMEIRA').count()
        equipamentos_count = Equipamento.objects.count()
        apontamentos_count = Apontamento.objects.count()
        
        context = {
            'total_clientes': clientes_count,
            'total_equipamentos': equipamentos_count,
            'total_apontamentos': apontamentos_count,
        }
        return render(request, 'clientes/confirm_delete_all.html', context)
    
    def post(self, request):
        confirmacao = request.POST.get('confirmacao', '').strip()
        if confirmacao != 'CONFIRMO':
            messages.error(request, 'Confirmação inválida. Digite exatamente "CONFIRMO".')
            return redirect('semeq:cliente_excluir_todos')
        
        from user.models import Apontamento, Equipamento, Cliente
        
        # Preserva o cliente padrão SEMEQ LIMEIRA
        cliente_padrao = Cliente.objects.filter(corporation='SEMEQ', plant='LIMEIRA').first()
        
        # Count before deletion (excluindo o padrão)
        clientes_para_excluir = Cliente.objects.exclude(corporation='SEMEQ', plant='LIMEIRA')
        clientes_count = clientes_para_excluir.count()
        equipamentos_count = Equipamento.objects.count()
        apontamentos_count = Apontamento.objects.count()
        
        # Delete in correct order (FK PROTECT)
        # First delete apontamentos of clients to be deleted
        Apontamento.objects.filter(cliente__in=clientes_para_excluir).delete()
        Equipamento.objects.all().delete()
        clientes_para_excluir.delete()
        
        messages.success(
            request, 
            f'Exclusão completa: {clientes_count} clientes, {equipamentos_count} equipamentos, '
            f'{apontamentos_count} apontamentos removidos. Cliente padrão SEMEQ LIMEIRA preservado.'
        )
        return redirect('semeq:cadastro_clientes')


class ClienteImportView(ClientePermissionMixin, View):
    @method_decorator(rate_limit(rate='5/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = ClienteImportForm()
        return render(request, 'clientes/importar.html', {'form': form})

    def post(self, request):
        confirmar = request.POST.get('confirmar')

        if confirmar:
            import_data = request.session.pop('cliente_import_data', None)
            if not import_data:
                messages.error(request, 'Dados de importação expirados. Tente novamente.')
                return redirect('semeq:cliente_importar')

            atualizar = import_data.get('atualizar', True)
            rows = import_data.get('rows', [])
            ext = import_data.get('ext', 'csv')

            criados = 0
            atualizados = 0
            erros = []

            for i, row_data in enumerate(rows, start=2):
                try:
                    corp = fix_encoding(row_data.get('corporation', ''))
                    plant = fix_encoding(row_data.get('plant', ''))
                    zone = fix_encoding(row_data.get('zone', ''))
                    plant_id = fix_encoding(row_data.get('plant_id', ''))

                    if not corp or not plant:
                        erros.append(f'Linha {i}: Corporação e Planta são obrigatórios')
                        continue

                    # Try to find existing client by plant_id first (for unification)
                    if plant_id:
                        existing = Cliente.objects.filter(plant_id=plant_id).first()
                        if existing:
                            # Update existing client
                            existing.corporation = corp
                            existing.plant = plant
                            if zone:
                                existing.zone = zone
                            existing.save()
                            atualizados += 1
                            continue

                    # Standard logic: unique by corporation + plant + zone
                    obj, created = Cliente.objects.update_or_create(
                        corporation=corp,
                        plant=plant,
                        defaults={'zone': zone}
                    )
                    if created:
                        criados += 1
                    else:
                        atualizados += 1
                except Exception as e:
                    erros.append(f'Linha {i}: {str(e)}')

            messages.success(request, f'Importação concluída: {criados} criados, {atualizados} atualizados.')
            if erros:
                # Agrupa erros iguais para não repetir
                from collections import Counter
                error_counts = Counter(erros)
                error_msgs = [f'{msg} ({count}x)' if count > 1 else msg for msg, count in error_counts.items()]
                messages.warning(request, 'Erros: ' + '; '.join(error_msgs[:10]) + ('...' if len(error_msgs) > 10 else ''))
            return redirect('semeq:cadastro_clientes')

        form = ClienteImportForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = form.cleaned_data['arquivo']
            atualizar = form.cleaned_data['atualizar_existentes']

            ext = arquivo.name.lower().split('.')[-1]
            headers, rows = parse_file(arquivo, ext)

            if not headers:
                messages.error(request, 'Arquivo vazio ou inválido.')
                return render(request, 'clientes/importar.html', {'form': form})

            normalized_rows = [normalize_row(r, headers) for r in rows]

            request.session['cliente_import_data'] = {
                'atualizar': atualizar,
                'rows': normalized_rows,
                'ext': ext,
            }

            preview = normalized_rows[:5]

            return render(request, 'clientes/importar.html', {
                'form': form,
                'preview': preview,
                'headers': headers,
                'total_rows': len(normalized_rows),
            })

        return render(request, 'clientes/importar.html', {'form': form})


class ClienteImportProcessView(LoginRequiredMixin, View):
    def post(self, request):
        return redirect('semeq:cliente_importar')


class ClienteFilterOptionsView(ClientePermissionMixin, View):
    """API endpoint for cascading filter options."""
    
    def get(self, request):
        field = request.GET.get('field', '')
        parent_field = request.GET.get('parent_field', '')
        parent_value = request.GET.get('parent_value', '')
        
        qs = Cliente.objects.all()
        
        if field == 'corporacoes':
            # All corporations
            data = list(qs.values('corporation').distinct().order_by('corporation'))
            return JsonResponse({'options': data})
        
        elif field == 'plantas':
            # Plants, optionally filtered by corporation_id
            if parent_field == 'corporation_id' and parent_value:
                qs = qs.filter(corporation_id=parent_value)
            data = list(qs.values('plant').distinct().order_by('plant')[:200])
            return JsonResponse({'options': data})
     
        # Default: return all
        corporacoes = list(qs.values('corporation').distinct().order_by('corporation'))
        plantas = list(qs.values('plant').distinct().order_by('plant')[:100])
        return JsonResponse({'corporacoes': corporacoes, 'plantas': plantas})


class ClienteCorporacoesAutocompleteView(LoginRequiredMixin, View):
    """Autocomplete para buscar Corporações únicas (para o campo Corporação do Apontamento)."""
    
    def get(self, request):
        q = request.GET.get('q', '').strip()
        qs = Cliente.objects.all().values(
            'corporation_id', 'corporation'
        ).distinct().order_by('corporation')
        
        if q:
            qs = qs.filter(
                Q(corporation__icontains=q) |
                Q(corporation_id__icontains=q)
            )
        
        data = list(qs[:50])
        # Formato para TomSelect: value=corporation_id, text=corporation
        results = [
            {'value': item['corporation_id'], 'text': item['corporation']}
            for item in data
        ]
        return JsonResponse({'results': results})


class ClientePlantasAutocompleteView(LoginRequiredMixin, View):
    """Autocomplete para buscar Plantas de uma Corporação específica."""
    
    def get(self, request):
        corporacao_id = request.GET.get('corporacao_id', '').strip()
        q = request.GET.get('q', '').strip()
        
        if not corporacao_id:
            return JsonResponse({'results': []})
        
        qs = Cliente.objects.filter(
            corporation_id=corporacao_id
        ).values('plant_id', 'plant').distinct().order_by('plant')
        
        if q:
            qs = qs.filter(
                Q(plant__icontains=q) |
                Q(plant_id__icontains=q)
            )
        
        data = list(qs[:50])
        # Formato para TomSelect: value=plant_id, text=plant
        results = [
            {'value': item['plant_id'], 'text': item['plant']}
            for item in data
        ]
        return JsonResponse({'results': results})


class ClienteAutocompleteView(LoginRequiredMixin, View):
    """Autocomplete search para o formulário de apontamento (qualquer usuário logado).
    O form de criação exige que colaboradores/líderes possam selecionar cliente/planta."""
    
    def get(self, request):
        q = request.GET.get('q', '').strip()
        qs = Cliente.objects.all()
        if q:
            qs = qs.filter(
                Q(corporation__icontains=q) |
                Q(plant__icontains=q) 
            )
        # Retornar formato esperado pelo TomSelect: value e text
        data = list(qs.values('pk', 'corporation', 'plant')[:50])
        results = []
        for item in data:
            value = str(item['pk'])
            text = f"{item['corporation']} - {item['plant']}"
            results.append({
                'value': value,
                'text': text,
                'corporation': item['corporation'],
                'plant': item['plant'],
            })
        return JsonResponse({'results': results}, json_dumps_params={'ensure_ascii': False})


class ClienteBuscaView(LoginRequiredMixin, View):
    """
    Autocomplete simples para busca de clientes via Fetch API.
    Retorna: [{"id": 1, "nome": "Corporação - Planta"}, ...]
    Vazio retorna todos (até 50). Com query filtra por corporation/plant.
    """
    
    def get(self, request):
        q = request.GET.get('q', '').strip()
        qs = Cliente.objects.all()
        if q:
            qs = qs.filter(
                Q(corporation__icontains=q) |
                Q(plant__icontains=q) 
            )
        # Limite menor para performance
        data = list(qs.values('pk', 'corporation', 'plant')[:50])
        results = [
            {'id': item['pk'], 'nome': f"{item['corporation']} - {item['plant']}"}
            for item in data
        ]
        return JsonResponse(results, safe=False, json_dumps_params={'ensure_ascii': False})


def buscar_clientes(request):
    """
    Autocomplete de clientes - retorna JSON para <datalist>
    GET /buscar-clientes/?q=termo
    Retorna: [{"id": 1, "label": "Corporação - Planta"}, ...] (max 10)
    """
    q = request.GET.get('q', '').strip()
    qs = Cliente.objects.all()
    if q:
        qs = qs.filter(
            Q(corporation__icontains=q) |
            Q(plant__icontains=q)
        )
    data = list(qs.values('pk', 'corporation', 'plant')[:10])
    results = [
        {'id': item['pk'], 'label': f"{item['corporation']} - {item['plant']}"}
        for item in data
    ]
    return JsonResponse(results, safe=False, json_dumps_params={'ensure_ascii': False})


def buscar_corporacoes(request):
    """
    Retorna corporações únicas para o primeiro select
    GET /buscar-corporacoes/
    Retorna: [{"corporation": "NOME"}, ...]
    """
    corporacoes = Cliente.objects.values('corporation').distinct().order_by('corporation')
    data = list(corporacoes)
    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


def buscar_plantas(request):
    """
    Retorna plantas de uma corporação específica
    GET /buscar-plantas/?corporacao=NOME
    Retorna: [{"id": 1, "plant": "PLANTA"}, ...]
    """
    corporacao = request.GET.get('corporacao', '').strip()
    if not corporacao:
        return JsonResponse([], safe=False, json_dumps_params={'ensure_ascii': False})
    
    plantas = Cliente.objects.filter(corporation=corporacao).values('pk', 'plant').order_by('plant')
    data = list(plantas)
    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


def buscar_cliente_detalhe(request):
    """
    Retorna detalhes de um cliente específico (para edição)
    GET /buscar-cliente-detalhe/?id=PK
    Retorna: {"id": 1, "corporation": "CORP", "plant": "PLANT"}
    """
    cliente_id = request.GET.get('id', '').strip()
    if not cliente_id:
        return JsonResponse({}, safe=False, json_dumps_params={'ensure_ascii': False})
    
    try:
        cliente = Cliente.objects.values('pk', 'corporation', 'plant').get(pk=cliente_id)
        return JsonResponse(cliente, json_dumps_params={'ensure_ascii': False})
    except Cliente.DoesNotExist:
        return JsonResponse({}, safe=False, json_dumps_params={'ensure_ascii': False})


class EquipamentoAutocompleteView(LoginRequiredMixin, View):
    """Autocomplete search for equipamentos."""
    
    def get(self, request):
        q = request.GET.get('q', '').strip()
        qs = Equipamento.objects.all()
        
        if q:
            qs = qs.filter(
                Q(id__icontains=q) |
                Q(nome__icontains=q) |
                Q(descricao__icontains=q)
            )
        
        data = list(qs.values('pk', 'nome', 'descricao')[:50])
        # Formato para TomSelect
        results = [
            {
                'value': item['pk'],
                'text': item['nome'] or str(item['pk']),
                'equipamento_id': str(item['pk']),
                'nome': item['nome'] or '',
                'descricao': item['descricao'] or '',
            }
            for item in data
        ]
        return JsonResponse({'results': results})


# Usuario Views
class UsuarioPermissionMixin(LoginRequiredMixin):
    """Apenas Admin e Gestor podem gerenciar usuários."""
    def dispatch(self, request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.can_manage_users())):
            messages.error(request, 'Acesso negado. Apenas administradores e gestores.')
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)


class UsuarioListView(UsuarioPermissionMixin, ListView):
    model = User
    template_name = 'usuarios/lista.html'
    context_object_name = 'usuarios'
    paginate_by = 20
    
    def get_queryset(self):
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        is_admin = self.request.user.is_superuser or (perfil and perfil.is_admin())
        
        qs = User.objects.select_related('perfil', 'perfil__equipe')
        
        if perfil and perfil.is_gestor_or_above():
            # Gestor/Admin sees ALL users (including superusers, admins, without perfil, inativo)
            pass
        elif perfil and perfil.is_lider_or_above():
            # Líder sees only active users in their team
            qs = qs.filter(perfil__ativo=True, perfil__equipe=perfil.equipe)
        else:
            # Colaborador sees only themselves
            qs = qs.filter(id=self.request.user.id)
        
        # Filtros
        search = self.request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        role = self.request.GET.get('role', '').strip()
        if role:
            qs = qs.filter(perfil__role=role)
        
        equipe_id = self.request.GET.get('equipe', '').strip()
        if equipe_id:
            qs = qs.filter(perfil__equipe_id=equipe_id)
        
        return qs.order_by('-perfil__criado_em')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = PerfilUsuario.ROLE_CHOICES
        context['times'] = Equipe.objects.filter(ativo=True)
        context['role_filter'] = self.request.GET.get('role', '')
        context['time_filter'] = self.request.GET.get('equipe', '')
        context['search'] = self.request.GET.get('q', '')
        return context


class UsuarioCreateView(UsuarioPermissionMixin, CreateView):
    model = User
    form_class = UsuarioForm
    template_name = 'cadastros/usuario_form.html'
    success_url = reverse_lazy('semeq:cadastro_usuarios')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        from django.db import transaction
        import logging
        logger = logging.getLogger('user')
        
        with transaction.atomic():
            # Let the form handle user creation with password and PerfilUsuario
            user = form.save()
            
            logger.info(f'[UsuarioCreateView] Usuário criado: {user.username} (ID: {user.pk}), Email: {user.email}, Perfil: {user.perfil.role}, Ativo: {user.is_active}, PerfilAtivo: {user.perfil.ativo}')
            
        messages.success(self.request, 'Usuário criado com sucesso!')
        return redirect(self.get_success_url())


class UsuarioUpdateView(UsuarioPermissionMixin, UpdateView):
    model = User
    form_class = UsuarioUpdateForm
    template_name = 'cadastros/usuario_form.html'
    success_url = reverse_lazy('semeq:cadastro_usuarios')
    
    def get_queryset(self):
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        is_admin = self.request.user.is_superuser or (perfil and perfil.is_admin())
        
        qs = User.objects.select_related('perfil', 'perfil__equipe')
        
        if perfil and perfil.is_gestor_or_above():
            # Gestor/Admin can edit ALL users (including superusers, admins, without perfil, inativo)
            pass
        elif perfil and perfil.is_lider_or_above():
            # Líder can only edit active users in their team
            qs = qs.filter(perfil__ativo=True, perfil__equipe=perfil.equipe)
        else:
            qs = qs.filter(id=self.request.user.id)
        
        return qs
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        return obj
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        import logging
        logger = logging.getLogger('user')
        
        # Check if password was changed
        password_changed = bool(form.cleaned_data.get('password'))
        
        response = super().form_valid(form)
        
        logger.info(f'[UsuarioUpdateView] Usuário atualizado: {self.object.username} (ID: {self.object.pk}) por {self.request.user.username}, Senha alterada: {password_changed}')
        
        messages.success(self.request, 'Usuário atualizado com sucesso!')
        return response


class UsuarioDeleteView(UsuarioPermissionMixin, DeleteView):
    model = User
    template_name = 'usuarios/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastro_usuarios')
    
    def get_queryset(self):
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        is_admin = self.request.user.is_superuser or (perfil and perfil.is_admin())
        
        qs = User.objects.select_related('perfil', 'perfil__equipe')
        
        if perfil and perfil.is_gestor_or_above():
            if not is_admin:
                qs = qs.exclude(is_superuser=True).exclude(perfil__role='admin')
        elif perfil and perfil.is_lider_or_above():
            qs = qs.filter(perfil__ativo=True, perfil__equipe=perfil.equipe)
        else:
            qs = qs.filter(id=self.request.user.id)
        
        return qs
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Impede auto-exclusão
        if obj == self.request.user:
            messages.error(self.request, 'Você não pode excluir seu próprio usuário.')
            raise PermissionDenied
        # Impede exclusão de admins/superusers
        if obj.is_superuser or (hasattr(obj, 'perfil') and obj.perfil.role == 'admin'):
            messages.error(self.request, 'Não é possível excluir usuários administradores.')
            raise PermissionDenied
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Count related apontamentos
        from user.models import Apontamento
        user = self.object
        context['apontamentos_count'] = Apontamento.objects.filter(responsavel=user).count()
        # Check if current user is admin
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        context['is_admin'] = self.request.user.is_superuser or (perfil and perfil.is_admin())
        context['show_delete_apontamentos_checkbox'] = context['is_admin'] and context['apontamentos_count'] > 0
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Check if target is admin/superuser
        if self.object.is_superuser or (hasattr(self.object, 'perfil') and self.object.perfil.role == 'admin'):
            messages.error(request, 'Não é possível excluir usuários administradores.')
            return redirect('semeq:cadastro_usuarios')
        
        delete_apontamentos = request.POST.get('delete_apontamentos') == 'on'
        
        # Count apontamentos
        from user.models import Apontamento
        apontamentos_count = Apontamento.objects.filter(responsavel=self.object).count()
        
        if apontamentos_count > 0:
            # Check if admin
            perfil = request.user.perfil if hasattr(request.user, 'perfil') else None
            is_admin = request.user.is_superuser or (perfil and perfil.is_admin())
            
            if not is_admin:
                messages.error(request,
                    f'Este usuário possui {apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir usuários com apontamentos.'
                )
                return redirect('semeq:cadastro_usuarios')
            
            if not delete_apontamentos:
                messages.error(request,
                    f'Este usuário possui {apontamentos_count} apontamento(s). '
                    'Marque a opção para excluir os apontamentos junto com o usuário.'
                )
                return self.get(request)
            
            # Admin confirmed - delete apontamentos first
            Apontamento.objects.filter(responsavel=self.object).delete()
        
        # Delete PerfilUsuario if exists, then delete User
        if hasattr(self.object, 'perfil'):
            self.object.perfil.delete()
        self.object.delete()
        messages.success(request, 'Usuário excluído com sucesso!')
        return redirect(self.get_success_url())
    
    def delete(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


# Configurações Views
class ConfiguracoesView(LoginRequiredMixin, View):
    """Tela única de configurações (gerais + perfil)."""

    def get(self, request):
        return render(request, 'configuracoes.html', {
            'perfil': getattr(request.user, 'perfil', None),
        })

    def post(self, request):
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        email = request.POST.get('email', '').strip()
        telefone = request.POST.get('telefone', '').strip()

        if username:
            username = username.lower()
            if not (username.isalnum() or '_' in username or '-' in username or '.' in username):
                messages.error(request, 'Usuário inválido. Use letras, números, ponto, hífen ou sublinhado.')
                return redirect('semeq:configuracoes')
            # Unicidade: não pode ser igual ao username de outro usuário
            existe = User.objects.exclude(pk=request.user.pk).filter(username__iexact=username).exists()
            if existe:
                messages.error(request, 'Este nome de usuário já está em uso.')
                return redirect('semeq:configuracoes')
            request.user.username = username

        if first_name:
            request.user.first_name = first_name
        if email:
            request.user.email = email
        request.user.save()

        perfil = getattr(request.user, 'perfil', None)
        if perfil and telefone is not None:
            perfil.telefone = telefone
            perfil.save()

        messages.success(request, 'Perfil atualizado com sucesso!')
        return redirect('semeq:configuracoes')


class ConfiguracoesTemaView(LoginRequiredMixin, View):
    """Endpoint AJAX para alternar tema light/dark."""

    @method_decorator(rate_limit(rate='30/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        import json
        try:
            data = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            data = {}
        tema = data.get('tema', '')
        if tema not in ['light', 'dark']:
            return JsonResponse({'success': False, 'message': 'Tema inválido.'}, status=400)

        perfil = getattr(request.user, 'perfil', None)
        if perfil:
            perfil.tema_preferido = tema
            perfil.save()

        return JsonResponse({'success': True, 'message': 'Tema atualizado!', 'tema': tema})


# =====================================================================
# PUBLIC REGISTRATION & PASSWORD RESET (apenas domínios permitidos)
# =====================================================================


class PublicRegistrationView(CreateView):
    """Cadastro público - apenas emails de domínios permitidos"""
    form_class = PublicRegistrationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('semeq:login')
    
    @method_decorator(rate_limit(rate='20/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.conf import settings
        context['allowed_domains'] = getattr(settings, 'ALLOWED_EMAIL_DOMAINS', ['semeq.com'])
        return context
    
    def form_valid(self, form):
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f'[PublicRegistrationView] Iniciando cadastro - Email: {form.cleaned_data.get("email")}, Nome: {form.cleaned_data.get("first_name")} {form.cleaned_data.get("last_name")}')
        
        response = super().form_valid(form)
        
        if hasattr(self, 'object') and self.object:
            logger.info(f'[PublicRegistrationView] Usuário criado com sucesso - ID: {self.object.pk}, Username: {self.object.username}, Email: {self.object.email}')
        else:
            logger.warning(f'[PublicRegistrationView] Usuário não criado (object não definido)')
        
        return response


class PublicRegistrationDoneView(View):
    """Redireciona para login após cadastro"""
    def get(self, request):
        return redirect('semeq:login')


class CustomLoginView(LoginView):
    """Login customizado usando email."""
    form_class = EmailLoginForm
    template_name = 'registration/login.html'
    redirect_authenticated_user = True
    
    @method_decorator(rate_limit(rate='10/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Email ou senha inválidos.')
        return super().form_invalid(form)


# Password Reset Views usando formulário customizado
class SemeqPasswordResetView(PasswordResetView):
    form_class = SemeqPasswordResetForm
    template_name = 'registration/password_reset.html'
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = reverse_lazy('semeq:password_reset_done')
    
    @method_decorator(rate_limit(rate='3/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class SemeqPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'registration/password_reset_done.html'


class SemeqPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('semeq:password_reset_complete')
    
    @method_decorator(rate_limit(rate='5/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class SemeqPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'registration/password_reset_complete.html'


# Custom error handlers
def custom_404(request, exception):
    return render(request, 'errors/404.html', status=404)


def custom_500(request):
    return render(request, 'errors/500.html', status=500)


# Custom LogoutView that accepts GET (for easier logout links)
class CustomLogoutView(LogoutView):
    http_method_names = ['get', 'post', 'options']
    
    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


class EquipamentoPermissionMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.can_manage_equipamentos())):
            messages.error(request, 'Acesso negado. Você não pode gerenciar equipamentos.')
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)


class EquipamentoListView(EquipamentoPermissionMixin, ListView):
    model = Equipamento
    template_name = 'equipamentos/lista.html'
    context_object_name = 'equipamentos'
    paginate_by = 20

    def get_queryset(self):
        qs = Equipamento.objects.all()
        filters = {
            'nome': self.request.GET.get('nome', '').strip(),
            'descricao': self.request.GET.get('descricao', '').strip(),
        }
        if filters['nome']:
            qs = qs.filter(nome__icontains=filters['nome'])
        if filters['descricao']:
            qs = qs.filter(descricao__icontains=filters['descricao'])
        return qs.order_by('-criado_em')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
            'nome': self.request.GET.get('nome', ''),
            'descricao': self.request.GET.get('descricao', ''),
        }
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filter_params'] = params.urlencode()
        return context


class EquipamentoCreateView(EquipamentoPermissionMixin, CreateView):
    model = Equipamento
    form_class = EquipamentoForm
    template_name = 'cadastros/equipamento_form.html'
    success_url = reverse_lazy('semeq:cadastro_equipamentos')

    def form_valid(self, form):
        messages.success(self.request, 'Equipamento criado com sucesso!')
        return super().form_valid(form)


class EquipamentoUpdateView(EquipamentoPermissionMixin, UpdateView):
    model = Equipamento
    form_class = EquipamentoForm
    template_name = 'cadastros/equipamento_form.html'
    success_url = reverse_lazy('semeq:cadastro_equipamentos')

    def form_valid(self, form):
        messages.success(self.request, 'Equipamento atualizado com sucesso!')
        return super().form_valid(form)


class EquipamentoDeleteView(EquipamentoPermissionMixin, DeleteView):
    model = Equipamento
    template_name = 'equipamentos/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastros_unificada')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Equipamento excluído com sucesso!')
        return super().delete(request, *args, **kwargs)
# =====================================================================
# STATUS CRUD
# =====================================================================

class StatusListView(PermissionMixin, BaseCRUDListView):
    model = Status
    template_name = 'cadastros/status_lista.html'
    context_object_name = 'status'
    search_fields = ['status']

    def get_queryset(self):
        return super().get_queryset().order_by('-criado_em')


class StatusCreateView(PermissionMixin, BaseCRUDCreateView):
    model = Status
    form_class = StatusForm
    template_name = 'cadastros/status_form.html'
    success_url = reverse_lazy('semeq:cadastro_status')


class StatusUpdateView(PermissionMixin, BaseCRUDUpdateView):
    model = Status
    form_class = StatusForm
    template_name = 'cadastros/status_form.html'
    success_url = reverse_lazy('semeq:cadastro_status')


class StatusDeleteView(PermissionMixin, DeleteView):
    model = Status
    template_name = 'status/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastros_unificada')
    
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.apontamentos_count = self.object.apontamento_set.count()
        
        # Impede exclusão de status fixos do sistema
        if self.object.is_fixo:
            messages.error(request, 
                'Status fixo do sistema não pode ser excluído. '
                'Apenas a cor e a ordem podem ser alteradas.'
            )
            return redirect('semeq:cadastro_status')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamentos_count'] = self.apontamentos_count
        context['is_admin'] = self.request.user.is_superuser or (
            hasattr(self.request.user, 'perfil') and self.request.user.perfil.is_admin()
        )
        context['is_fixo'] = self.object.is_fixo
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Impede exclusão de status fixos do sistema
        if self.object.is_fixo:
            messages.error(request, 
                'Status fixo do sistema não pode ser excluído. '
                'Apenas a cor e a ordem podem ser alteradas.'
            )
            return redirect('semeq:cadastro_status')
        
        if self.apontamentos_count > 0:
            if not (request.user.is_superuser or (
                hasattr(request.user, 'perfil') and request.user.perfil.is_admin()
            )):
                messages.error(request, 
                    f'Este status possui {self.apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir status com apontamentos.'
                )
                return redirect('semeq:cadastros_unificada')
            
            self.object.apontamento_set.all().delete()
        
        messages.success(request, 'Status excluído com sucesso!')
        return super().post(request, *args, **kwargs)

# =====================================================================
# ATIVIDADE CRUD
# =====================================================================

class AtividadePermissionMixin(LoginRequiredMixin):
    """Apenas Admin e Gestor podem gerenciar Atividades."""
    def dispatch(self, request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.is_gestor_or_above())):
            messages.error(request, 'Acesso negado. Apenas administradores e gestores.')
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)


# =====================================================================
# ATIVIDADE CRUD
# =====================================================================

class AtividadePermissionMixin(LoginRequiredMixin):
    """Apenas Admin e Gestor podem gerenciar Atividades."""
    def dispatch(self, request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.is_gestor_or_above())):
            messages.error(request, 'Acesso negado. Apenas administradores e gestores.')
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)


# =====================================================================
# ATIVIDADE CRUD
# =====================================================================

class AtividadeListView(PermissionMixin, BaseCRUDListView):
    model = Atividade
    template_name = 'cadastros/atividade_lista.html'
    context_object_name = 'atividades'
    search_fields = ['nome']

    def get_queryset(self):
        return super().get_queryset().order_by('-criado_em')


class AtividadeCreateView(PermissionMixin, BaseCRUDCreateView):
    model = Atividade
    form_class = AtividadeForm
    template_name = 'cadastros/atividade_form.html'
    success_url = reverse_lazy('semeq:cadastro_atividades')


class AtividadeUpdateView(PermissionMixin, BaseCRUDUpdateView):
    model = Atividade
    form_class = AtividadeForm
    template_name = 'cadastros/atividade_form.html'
    success_url = reverse_lazy('semeq:cadastro_atividades')


class AtividadeDeleteView(PermissionMixin, DeleteView):
    model = Atividade
    template_name = 'atividade/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastros_unificada')
    
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.apontamentos_count = self.object.apontamento_set.count()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamentos_count'] = self.apontamentos_count
        context['is_admin'] = self.request.user.is_superuser or (
            hasattr(self.request.user, 'perfil') and self.request.user.perfil.is_admin()
        )
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        if self.apontamentos_count > 0:
            if not (request.user.is_superuser or (
                hasattr(request.user, 'perfil') and request.user.perfil.is_admin()
            )):
                messages.error(request, 
                    f'Esta atividade possui {self.apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir atividades com apontamentos.'
)
                return redirect('semeq:cadastros_unificada')
            
            self.object.apontamento_set.all().delete()
        
        messages.success(request, 'Atividade excluída com sucesso!')
        return super().post(request, *args, **kwargs)


# =====================================================================
# PRIORIDADE CRUD
# =====================================================================

class PrioridadeListView(PermissionMixin, BaseCRUDListView):
    model = Prioridade
    template_name = 'cadastros/prioridade_lista.html'
    context_object_name = 'prioridades'
    search_fields = ['nome']

    def get_queryset(self):
        return super().get_queryset().order_by('-criado_em')


class PrioridadeCreateView(PermissionMixin, BaseCRUDCreateView):
    model = Prioridade
    form_class = PrioridadeForm
    template_name = 'cadastros/prioridade_form.html'
    success_url = reverse_lazy('semeq:cadastro_prioridades')


class PrioridadeUpdateView(PermissionMixin, BaseCRUDUpdateView):
    model = Prioridade
    form_class = PrioridadeForm
    template_name = 'cadastros/prioridade_form.html'
    success_url = reverse_lazy('semeq:cadastro_prioridades')


class PrioridadeDeleteView(PermissionMixin, DeleteView):
    model = Prioridade
    template_name = 'prioridade/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastros_unificada')
    
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.apontamentos_count = self.object.apontamento_set.count()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamentos_count'] = self.apontamentos_count
        context['is_admin'] = self.request.user.is_superuser or (
            hasattr(self.request.user, 'perfil') and self.request.user.perfil.is_admin()
        )
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        if self.apontamentos_count > 0:
            if not (request.user.is_superuser or (
                hasattr(request.user, 'perfil') and request.user.perfil.is_admin()
            )):
                messages.error(request, 
                    f'Esta prioridade possui {self.apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir prioridades com apontamentos.'
                )
                return redirect('semeq:cadastros_unificada')
            
            self.object.apontamento_set.all().delete()
        
        messages.success(request, 'Prioridade excluída com sucesso!')
        return super().post(request, *args, **kwargs)


# =====================================================================
# EQUIPE CRUD
# =====================================================================

class EquipeListView(PermissionMixin, BaseCRUDListView):
    model = Equipe
    template_name = 'cadastros/equipe_lista.html'
    context_object_name = 'equipes'
    search_fields = ['nome']

    def get_queryset(self):
        return super().get_queryset().order_by('-criado_em')


class EquipeCreateView(PermissionMixin, BaseCRUDCreateView):
    model = Equipe
    form_class = EquipeForm
    template_name = 'cadastros/equipe_form.html'
    success_url = reverse_lazy('semeq:cadastro_equipes')


class EquipeUpdateView(PermissionMixin, BaseCRUDUpdateView):
    model = Equipe
    form_class = EquipeForm
    template_name = 'cadastros/equipe_form.html'
    success_url = reverse_lazy('semeq:cadastro_equipes')


class EquipeDeleteView(PermissionMixin, DeleteView):
    model = Equipe
    template_name = 'equipe/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastros_unificada')
    
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.apontamentos_count = self.object.apontamento_set.count()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamentos_count'] = self.apontamentos_count
        context['is_admin'] = self.request.user.is_superuser or (
            hasattr(request.user, 'perfil') and self.request.user.perfil.is_admin()
        )
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        if self.apontamentos_count > 0:
            if not (request.user.is_superuser or (
                hasattr(request.user, 'perfil') and request.user.perfil.is_admin()
            )):
                messages.error(request, 
                    f'Esta equipe possui {self.apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir equipes com apontamentos.'
                )
                return redirect('semeq:cadastros_unificada')
            
            self.object.apontamento_set.all().delete()
        
        messages.success(request, 'Equipe excluída com sucesso!')
        return super().post(request, *args, **kwargs)


# =====================================================================
# CADASTROS - PÁGINA PRINCIPAL (Hub /cadastros/)
# =====================================================================

class CadastrosUnificadaView(LoginRequiredMixin, View):
    """Hub de navegação de cadastros - Grid de cards com contadores."""
    
    def get(self, request):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.is_gestor_or_above())):
            messages.error(request, 'Acesso negado. Apenas administradores e gestores.')
            return redirect('semeq:dashboard')
        
        # Apenas contadores para os cards do hub
        cliente_count = Cliente.objects.count()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        usuario_count = User.objects.count()  # Show ALL users (incl. inativos, sem perfil)
        equipe_count = Equipe.objects.count()
        equipamento_count = Equipamento.objects.count()
        status_count = Status.objects.count()
        atividade_count = Atividade.objects.count()
        prioridade_count = Prioridade.objects.count()
        tipoproblema_count = TipoProblema.objects.count()
        projeto_count = Projeto.objects.count()
        solicitante_count = Solicitante.objects.count()
        
        return render(request, 'cadastros/unificada.html', {
            'perfil': perfil,
            # Contadores para os cards
            'cliente_count': cliente_count,
            'usuario_count': usuario_count,
            'equipe_count': equipe_count,
            'equipamento_count': equipamento_count,
            'status_count': status_count,
            'atividade_count': atividade_count,
            'prioridade_count': prioridade_count,
            'tipoproblema_count': tipoproblema_count,
            'projeto_count': projeto_count,
            'solicitante_count': solicitante_count,
            # URLs das páginas individuais
            'url_cliente_lista': reverse_lazy('semeq:cadastro_clientes'),
            'url_usuario_lista': reverse_lazy('semeq:cadastro_usuarios'),
            'url_equipe_lista': reverse_lazy('semeq:cadastro_equipes'),
            'url_equipamento_lista': reverse_lazy('semeq:cadastro_equipamentos'),
            'url_cadastro_status': reverse_lazy('semeq:cadastro_status'),
            'url_atividade_lista': reverse_lazy('semeq:cadastro_atividades'),
            'url_prioridade_lista': reverse_lazy('semeq:cadastro_prioridades'),
            'url_tipoproblema_lista': reverse_lazy('semeq:cadastro_tipoproblemas'),
            'url_projeto_lista': reverse_lazy('semeq:cadastro_projetos'),
            'url_solicitante_lista': reverse_lazy('semeq:cadastro_solicitantes'),
            # URLs para "Novo" (podem ser usadas nos cards se necessário)
            'url_cliente_novo': reverse_lazy('semeq:cliente_novo'),
            'url_equipe_novo': reverse_lazy('semeq:equipe_novo'),
            'url_equipamento_novo': reverse_lazy('semeq:equipamento_novo'),
            'url_cliente_importar': reverse_lazy('semeq:cliente_importar'),
            'url_status_novo': reverse_lazy('semeq:status_novo'),
            'url_atividade_novo': reverse_lazy('semeq:atividade_novo'),
            'url_prioridade_novo': reverse_lazy('semeq:prioridade_novo'),
            'url_tipoproblema_novo': reverse_lazy('semeq:tipoproblema_novo'),
            'url_projeto_novo': reverse_lazy('semeq:projeto_novo'),
            'url_solicitante_novo': reverse_lazy('semeq:solicitante_novo'),
        })

# =====================================================================
# CADASTROS INDIVIDUAIS (Novas páginas /cadastros/<model>/)
# =====================================================================

class CadastroBaseView(LoginRequiredMixin, View):
    """Base para páginas de cadastro individuais com busca e paginação."""
    model = None
    template_name = None
    search_fields = []
    context_object_name = 'object_list'
    create_url_name = None
    import_url_name = None
    title = ''
    icon = ''
    paginate_by = 20
    edit_url_name = None
    delete_url_name = None
    
    def dispatch(self, request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.is_gestor_or_above())):
            messages.error(request, 'Acesso negado. Apenas administradores e gestores.')
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        qs = self.model.objects.all()
        
        # Search
        q = self.request.GET.get('q', '').strip()
        if q and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": q})
            qs = qs.filter(query)
        
        # Ordering
        ordering = getattr(self.model._meta, 'ordering', ['-criado_em'])
        if ordering:
            qs = qs.order_by(*ordering)
        
        return qs
    
    def get_context_data(self, **kwargs):
        q = self.request.GET.get('q', '').strip()
        page = self.request.GET.get('page', 1)
        
        from django.core.paginator import Paginator
        from django.http import QueryDict
        
        qs = self.get_queryset()
        paginator = Paginator(qs, self.paginate_by)
        page_obj = paginator.get_page(page)
        
        # Build delete URL path (e.g., 'clientes', 'usuarios', 'status', etc.)
        delete_url_path = self.get_tab_id()
        
        # Build filter params for pagination (exclude 'page')
        params = self.request.GET.copy()
        params.pop('page', None)
        filter_params = params.urlencode()
        
        context = {
            'perfil': getattr(self.request.user, 'perfil', None),
            'page_obj': page_obj,
            'paginator': paginator,
            'object_list': page_obj.object_list,
            'search': q,
            'filter_params': filter_params,
            'is_paginated': page_obj.has_other_pages(),
            'title': self.title,
            'icon': self.icon,
            'create_url': reverse_lazy(self.create_url_name) if self.create_url_name else None,
            'import_url': reverse_lazy(self.import_url_name) if self.import_url_name else None,
            'edit_url_name': self.edit_url_name,
            'delete_url_name': self.delete_url_name,
            'delete_url_path': delete_url_path,
            'current_tab': self.get_tab_id(),
        }
        context.update(kwargs)
        return context
    
    def get_tab_id(self):
        """Retorna o ID da tab para navegação."""
        # Map model names to URL path (plural forms)
        tab_map = {
            'Cliente': 'clientes',
            'User': 'usuarios',
            'Equipe': 'equipes',
            'Equipamento': 'equipamentos',
            'Status': 'status',
            'Atividade': 'atividades',
            'Prioridade': 'prioridades',
            'TipoProblema': 'tipoproblemas',
            'Projeto': 'projetos',
            'Solicitante': 'solicitantes',
        }
        return tab_map.get(self.model.__name__, self.model.__name__.lower())
    
    def get(self, request):
        context = self.get_context_data()
        return render(request, self.template_name, context)


class CadastroClienteView(CadastroBaseView):
    model = Cliente
    template_name = 'cadastros/cliente_lista.html'
    search_fields = ['corporation', 'plant', 'zone']
    title = 'Clientes'
    icon = 'bi-building'
    create_url_name = 'semeq:cliente_novo'
    import_url_name = 'semeq:cliente_importar'
    edit_url_name = 'semeq:cliente_editar'
    delete_url_name = 'semeq:cliente_excluir'
    paginate_by = 20
    create_label = 'Cliente'
    current_tab = 'clientes'


class CadastroUsuarioView(CadastroBaseView):
    model = User
    template_name = 'cadastros/usuario_lista.html'
    search_fields = ['username', 'first_name', 'last_name', 'email']
    title = 'Usuários'
    icon = 'bi-people'
    create_url_name = 'semeq:usuario_novo'
    edit_url_name = 'semeq:usuario_editar'
    delete_url_name = 'semeq:usuario_excluir'
    paginate_by = 20
    create_label = 'Usuário'
    current_tab = 'usuarios'
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Show ALL users (including inativos, sem perfil) for gestor/admin
        return qs.select_related(
            'perfil', 'perfil__equipe'
        ).order_by('first_name', 'last_name', 'username')


class CadastroEquipeView(CadastroBaseView):
    model = Equipe
    template_name = 'cadastros/equipe_lista.html'
    search_fields = ['nome']
    title = 'Equipes'
    icon = 'bi-people-fill'
    create_url_name = 'semeq:equipe_novo'
    edit_url_name = 'semeq:equipe_editar'
    delete_url_name = 'semeq:equipe_excluir'
    paginate_by = 20
    create_label = 'Equipe'
    current_tab = 'equipes'


class CadastroEquipamentoView(CadastroBaseView):
    model = Equipamento
    template_name = 'cadastros/equipamento_lista.html'
    search_fields = ['nome', 'descricao']
    title = 'Equipamentos'
    icon = 'bi-cpu'
    create_url_name = 'semeq:equipamento_novo'
    edit_url_name = 'semeq:equipamento_editar'
    delete_url_name = 'semeq:equipamento_excluir'
    paginate_by = 20
    create_label = 'Equipamento'
    current_tab = 'equipamentos'


# =====================================================================
# CADASTROS AUXILIARES (Status, Atividade, Prioridade, TipoProblema, Projeto, Solicitante)
# =====================================================================

class CadastroStatusView(CadastroBaseView):
    model = Status
    template_name = 'cadastros/status_lista.html'
    search_fields = ['status']
    title = 'Status'
    icon = 'bi-tag'
    create_url_name = 'semeq:status_novo'
    edit_url_name = 'semeq:status_editar'
    delete_url_name = 'semeq:status_excluir'
    paginate_by = 20
    create_label = 'Status'
    current_tab = 'status'


class CadastroAtividadeView(CadastroBaseView):
    model = Atividade
    template_name = 'cadastros/atividade_lista.html'
    search_fields = ['nome']
    title = 'Atividades'
    icon = 'bi-list-task'
    create_url_name = 'semeq:atividade_novo'
    edit_url_name = 'semeq:atividade_editar'
    delete_url_name = 'semeq:atividade_excluir'
    paginate_by = 20
    create_label = 'Atividade'
    current_tab = 'atividades'


class CadastroPrioridadeView(CadastroBaseView):
    model = Prioridade
    template_name = 'cadastros/prioridade_lista.html'
    search_fields = ['nome']
    title = 'Prioridades'
    icon = 'bi-flag'
    create_url_name = 'semeq:prioridade_novo'
    edit_url_name = 'semeq:prioridade_editar'
    delete_url_name = 'semeq:prioridade_excluir'
    paginate_by = 20
    create_label = 'Prioridade'
    current_tab = 'prioridades'


class CadastroTipoProblemaView(CadastroBaseView):
    model = TipoProblema
    template_name = 'cadastros/tipoproblema_lista.html'
    search_fields = ['nome', 'descricao']
    title = 'Tipos de Problema'
    icon = 'bi-exclamation-triangle'
    create_url_name = 'semeq:tipoproblema_novo'
    edit_url_name = 'semeq:tipoproblema_editar'
    delete_url_name = 'semeq:tipoproblema_excluir'
    paginate_by = 20
    create_label = 'Tipo de Problema'
    current_tab = 'tipoproblemas'


class CadastroProjetoView(CadastroBaseView):
    model = Projeto
    template_name = 'cadastros/projeto_lista.html'
    search_fields = ['nome']
    title = 'Projetos'
    icon = 'bi-folder'
    create_url_name = 'semeq:projeto_novo'
    edit_url_name = 'semeq:projeto_editar'
    delete_url_name = 'semeq:projeto_excluir'
    paginate_by = 20
    create_label = 'Projeto'
    current_tab = 'projetos'


class CadastroSolicitanteView(CadastroBaseView):
    model = Solicitante
    template_name = 'cadastros/solicitante_lista.html'
    search_fields = ['nome']
    title = 'Solicitantes'
    icon = 'bi-person-badge'
    create_url_name = 'semeq:solicitante_novo'
    edit_url_name = 'semeq:solicitante_editar'
    delete_url_name = 'semeq:solicitante_excluir'
    paginate_by = 20
    create_label = 'Solicitante'
    current_tab = 'solicitantes'


# =====================================================================
# TIPOPROBLEMA CRUD
# =====================================================================

class TipoProblemaListView(PermissionMixin, BaseCRUDListView):
    model = TipoProblema
    template_name = 'cadastros/tipoproblema_lista.html'
    context_object_name = 'tipos_problema'
    search_fields = ['nome', 'descricao']

    def get_queryset(self):
        return super().get_queryset().order_by('-criado_em')


class TipoProblemaCreateView(PermissionMixin, BaseCRUDCreateView):
    model = TipoProblema
    form_class = TipoProblemaForm
    template_name = 'cadastros/tipoproblema_form.html'
    success_url = reverse_lazy('semeq:cadastro_tipoproblemas')


class TipoProblemaUpdateView(PermissionMixin, BaseCRUDUpdateView):
    model = TipoProblema
    form_class = TipoProblemaForm
    template_name = 'cadastros/tipoproblema_form.html'
    success_url = reverse_lazy('semeq:cadastro_tipoproblemas')


class TipoProblemaDeleteView(PermissionMixin, DeleteView):
    model = TipoProblema
    template_name = 'tipoproblema/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastros_unificada')
    
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.apontamentos_count = self.object.apontamento_set.count()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamentos_count'] = self.apontamentos_count
        context['is_admin'] = self.request.user.is_superuser or (
            hasattr(self.request.user, 'perfil') and self.request.user.perfil.is_admin()
        )
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        if self.apontamentos_count > 0:
            if not (request.user.is_superuser or (
                hasattr(request.user, 'perfil') and request.user.perfil.is_admin()
            )):
                messages.error(request, 
                    f'Este tipo de problema possui {self.apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir tipos de problema com apontamentos.'
                )
                return redirect('semeq:cadastros_unificada')
            
            self.object.apontamento_set.all().delete()
        
        messages.success(request, 'Tipo de Problema excluído com sucesso!')
        return super().post(request, *args, **kwargs)


# =====================================================================
# PROJETO CRUD
# =====================================================================

class ProjetoListView(PermissionMixin, BaseCRUDListView):
    model = Projeto
    template_name = 'cadastros/projeto_lista.html'
    context_object_name = 'projetos'
    search_fields = ['nome']

    def get_queryset(self):
        return super().get_queryset().order_by('-criado_em')


class ProjetoCreateView(PermissionMixin, BaseCRUDCreateView):
    model = Projeto
    form_class = ProjetoForm
    template_name = 'cadastros/projeto_form.html'
    success_url = reverse_lazy('semeq:cadastro_projetos')


class ProjetoUpdateView(PermissionMixin, BaseCRUDUpdateView):
    model = Projeto
    form_class = ProjetoForm
    template_name = 'cadastros/projeto_form.html'
    success_url = reverse_lazy('semeq:cadastro_projetos')


class ProjetoDeleteView(PermissionMixin, DeleteView):
    model = Projeto
    template_name = 'projeto/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastros_unificada')
    
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.apontamentos_count = self.object.apontamento_set.count()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamentos_count'] = self.apontamentos_count
        context['is_admin'] = self.request.user.is_superuser or (
            hasattr(self.request.user, 'perfil') and self.request.user.perfil.is_admin()
        )
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        if self.apontamentos_count > 0:
            if not (request.user.is_superuser or (
                hasattr(request.user, 'perfil') and request.user.perfil.is_admin()
            )):
                messages.error(request, 
                    f'Este projeto possui {self.apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir projetos com apontamentos.'
                )
                return redirect('semeq:cadastros_unificada')
            
            self.object.apontamento_set.all().delete()
        
        messages.success(request, 'Projeto excluído com sucesso!')
        return super().post(request, *args, **kwargs)
    
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.apontamentos_count = self.object.apontamento_set.count()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamentos_count'] = self.apontamentos_count
        context['is_admin'] = self.request.user.is_superuser or (
            hasattr(request.user, 'perfil') and self.request.user.perfil.is_admin()
        )
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        if self.apontamentos_count > 0:
            if not (request.user.is_superuser or (
                hasattr(request.user, 'perfil') and self.request.user.perfil.is_admin()
            )):
                messages.error(request, 
                    f'Este projeto possui {self.apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir projetos com apontamentos.'
                )
                return redirect('semeq:cadastros_unificada')
            
            self.object.apontamento_set.all().delete()
        
        messages.success(request, 'Projeto excluído com sucesso!')
        return super().post(request, *args, **kwargs)


# =====================================================================
# SOLICITANTE CRUD
# =====================================================================

class SolicitanteListView(PermissionMixin, BaseCRUDListView):
    model = Solicitante
    template_name = 'solicitante/lista.html'
    context_object_name = 'solicitantes'
    search_fields = ['nome']

    def get_queryset(self):
        return super().get_queryset().order_by('-criado_em')


class SolicitanteCreateView(PermissionMixin, BaseCRUDCreateView):
    model = Solicitante
    form_class = SolicitanteForm
    template_name = 'cadastros/solicitante_form.html'
    success_url = reverse_lazy('semeq:cadastro_solicitantes')


class SolicitanteUpdateView(PermissionMixin, BaseCRUDUpdateView):
    model = Solicitante
    form_class = SolicitanteForm
    template_name = 'cadastros/solicitante_form.html'
    success_url = reverse_lazy('semeq:cadastro_solicitantes')


class SolicitanteDeleteView(PermissionMixin, DeleteView):
    model = Solicitante
    template_name = 'solicitante/confirm_delete.html'
    success_url = reverse_lazy('semeq:cadastros_unificada')
    
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.apontamentos_count = self.object.apontamento_set.count()
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apontamentos_count'] = self.apontamentos_count
        context['is_admin'] = self.request.user.is_superuser or (
            hasattr(request.user, 'perfil') and self.request.user.perfil.is_admin()
        )
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        if self.apontamentos_count > 0:
            if not (request.user.is_superuser or (
                hasattr(request.user, 'perfil') and self.request.user.perfil.is_admin()
            )):
                messages.error(request, 
                    f'Este solicitante possui {self.apontamentos_count} apontamento(s) associado(s). '
                    'Apenas administradores podem excluir solicitantes com apontamentos.'
                )
                return redirect('semeq:cadastros_unificada')
            
            self.object.apontamento_set.all().delete()
        
        messages.success(request, 'Solicitante excluído com sucesso!')
        return super().post(request, *args, **kwargs)


def csrf_failure(request, reason=''):
    """View customizada para falha de CSRF."""
    import logging
    logger = logging.getLogger('django.security.csrf')
    logger.warning(f'CSRF failure: {reason} - IP: {request.META.get("REMOTE_ADDR")} - Path: {request.path}')
    return render(request, 'errors/403_csrf.html', {'reason': reason}, status=403)


def api_zonas_por_corporacao(request):
    """API endpoint para buscar zonas por corporação."""
    corporacao_id = request.GET.get('corporation_id')
    
    if not corporacao_id:
        return JsonResponse({'zonas': []})
    
    zonas = list(Cliente.objects.filter(
        corporation=corporacao_id, ativo=True
    ).values_list('zone', flat=True).distinct().order_by('zone'))
    
    # Filter out empty/None zones
    zonas = [z for z in zonas if z]
    
    return JsonResponse({'zonas': zonas})


def api_plantas_por_corporacao_zona(request):
    """API endpoint para buscar plantas por corporação e zona."""
    corporacao_id = request.GET.get('corporation_id')
    zona = request.GET.get('zona')
    
    if not corporacao_id or not zona:
        return JsonResponse({'plantas': []})
    
    plantas = list(Cliente.objects.filter(
        corporation=corporacao_id, zone=zona, ativo=True
    ).values('pk', 'plant').order_by('plant'))
    
    return JsonResponse({'plantas': plantas})


def carregar_responsaveis(request):
    """API endpoint para carregar responsáveis filtrados por equipe."""
    equipe_id = request.GET.get('equipe_id')
    
    # Base queryset: usuários ativos com perfil ativo
    responsaveis = User.objects.filter(
        is_active=True, perfil__ativo=True
    ).select_related('perfil', 'perfil__equipe').order_by('first_name', 'username')
    
    if equipe_id:
        responsaveis = responsaveis.filter(perfil__equipe_id=equipe_id)
    
    data = [
        {
            'id': user.id,
            'nome': user.get_full_name() or user.username,
            'equipe_id': user.perfil.equipe_id if hasattr(user, 'perfil') and user.perfil.equipe_id else None
        }
        for user in responsaveis
    ]
    
    return JsonResponse(data, safe=False)


def api_zonas_por_corporacao(request):
    """API endpoint para buscar zonas por corporação."""
    corporacao_id = request.GET.get('corporation_id')
    
    if not corporacao_id:
        return JsonResponse({'zonas': []})
    
    zonas = list(Cliente.objects.filter(
        corporation=corporacao_id, ativo=True
    ).values_list('zone', flat=True).distinct().order_by('zone'))
    
    # Filter out empty/None zones
    zonas = [z for z in zonas if z]
    
    return JsonResponse({'zonas': zonas})


def api_plantas_por_corporacao_zona(request):
    """API endpoint para buscar plantas por corporação e zona."""
    corporacao_id = request.GET.get('corporation_id')
    zona = request.GET.get('zona')
    
    if not corporacao_id or not zona:
        return JsonResponse({'plantas': []})
    
    plantas = list(Cliente.objects.filter(
        corporation=corporacao_id, zone=zona, ativo=True
    ).values('pk', 'plant').order_by('plant'))
    
    return JsonResponse({'plantas': plantas})


def carregar_responsaveis(request):
    """API endpoint para carregar responsáveis filtrados por equipe."""
    equipe_id = request.GET.get('equipe_id')
    
    # Base queryset: usuários ativos com perfil ativo
    responsaveis = User.objects.filter(
        is_active=True, perfil__ativo=True
    ).select_related('perfil', 'perfil__equipe').order_by('first_name', 'username')
    
    if equipe_id:
        responsaveis = responsaveis.filter(perfil__equipe_id=equipe_id)
    
    data = [
        {
            'id': user.id,
            'nome': user.get_full_name() or user.username,
            'equipe_id': user.perfil.equipe_id if hasattr(user, 'perfil') and user.perfil.equipe_id else None
        }
        for user in responsaveis
    ]
    
    return JsonResponse(data, safe=False)


class HealthCheckView(View):
    """Health check endpoint para monitoramento (load balancer, k8s, etc)."""
    
    def get(self, request):
        from django.db import connection
        from django.core.cache import cache
        
        checks = {}
        status_code = 200
        
        # Database
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            checks['database'] = 'ok'
        except Exception as e:
            checks['database'] = f'error: {e}'
            status_code = 503
        
        # Cache
        try:
            cache.set('health_check', 'ok', 10)
            if cache.get('health_check') == 'ok':
                checks['cache'] = 'ok'
            else:
                checks['cache'] = 'error: cache not working'
                status_code = 503
        except Exception as e:
            checks['cache'] = f'error: {e}'
            status_code = 503
        
        return JsonResponse({
            'status': 'healthy' if status_code == 200 else 'unhealthy',
            'checks': checks,
        }, status=status_code)
