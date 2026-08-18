from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LogoutView
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, DurationField
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from datetime import date, timedelta, datetime
from .models import Cliente, Equipamento, PerfilUsuario, Time, Apontamento
from .forms import (
    ClienteForm, ClienteImportForm,
    UsuarioForm, ApontamentoForm, UsuarioUpdateForm, EquipamentoForm
)
from .throttle import rate_limit
import csv
import openpyxl
from io import BytesIO


def HomeView(request):
    return render(request, 'home/home.html')


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        perfil = request.user.perfil if hasattr(request.user, 'perfil') else None
        
        # Filtros
        time_id = request.GET.get('time')
        usuario_id = request.GET.get('usuario')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        status = request.GET.get('status')
        prioridade = request.GET.get('prioridade')
        
        # Base queryset
        qs = Apontamento.objects.select_related('cliente', 'responsavel', 'equipamento').all()
        
        # Permissões
        if perfil and perfil.is_lider_or_above() and not perfil.is_gestor_or_above():
            equipe_codigo = perfil.time.nome.lower() if perfil.time else ''
            qs = qs.filter(equipe=equipe_codigo) if equipe_codigo else qs.none()
        elif not perfil or not perfil.is_gestor_or_above():
            qs = qs.filter(responsavel=request.user)
        
        # Se não houver datas informadas, mostra a semana atual (segunda a domingo)
        if not data_inicio and not data_fim:
            seg = date.today() - timedelta(days=date.today().weekday())
            dom = seg + timedelta(days=6)
            qs = qs.filter(data__range=[seg, dom])
        
        # Aplicar filtros
        if time_id and perfil and perfil.is_gestor_or_above():
            equipe_nome = Time.objects.filter(
                pk=time_id, ativo=True
            ).values_list('nome', flat=True).first()
            if equipe_nome:
                qs = qs.filter(equipe=equipe_nome.lower())
            else:
                qs = qs.none()
        if usuario_id:
            qs = qs.filter(responsavel_id=usuario_id)
        if data_inicio:
            qs = qs.filter(data__gte=data_inicio)
        if data_fim:
            qs = qs.filter(data__lte=data_fim)
        if status:
            qs = qs.filter(status=status)
        if prioridade:
            qs = qs.filter(prioridade=prioridade)
        
        # KPIs
        hoje = date.today()
        total_hoje = qs.filter(data=hoje).count()
        
        horas_trabalhadas = qs.aggregate(total=Sum('tempo_total'))['total']
        if horas_trabalhadas:
            total_seconds = int(horas_trabalhadas.total_seconds())
            horas_str = f"{total_seconds // 3600}h {(total_seconds % 3600) // 60}m"
        else:
            horas_str = "0h 0m"
        
        em_aberto = qs.filter(status='aberto').count()
        
        concluidos = qs.filter(status='concluido').count()
        total_status = qs.exclude(status='cancelado').count()
        sla_pct = round((concluidos / total_status * 100), 1) if total_status > 0 else 0
        
        # Últimos 10 apontamentos
        ultimos = qs[:10]
        
        # Totais diários por usuário (para indicador de cumprimento)
        daily_totals = qs.values('responsavel__id', 'responsavel__first_name', 'responsavel__last_name', 'data').annotate(
            total_minutos=Sum(ExpressionWrapper(F('tempo_total'), output_field=DurationField()))
        ).order_by('-data')
        
        # Process daily totals for compliance check
        daily_compliance = {}
        for dt in daily_totals:
            user_id = dt['responsavel__id']
            data = dt['data']
            total_min = 0
            if dt['total_minutos']:
                total_min = int(dt['total_minutos'].total_seconds() / 60)
            
            weekday = data.weekday()
            min_required = 540 if weekday <= 3 else (480 if weekday == 4 else 0)
            compliant = total_min >= min_required if min_required > 0 else True
            
            key = f"{user_id}_{data}"
            daily_compliance[key] = {
                'user_id': user_id,
                'user_name': f"{dt['responsavel__first_name']} {dt['responsavel__last_name']}".strip(),
                'data': data,
                'total_minutos': total_min,
                'min_required': min_required,
                'compliant': compliant,
                'deficit': max(0, min_required - total_min) if min_required > 0 else 0,
            }
        
        # Para filtros
        if perfil and perfil.is_gestor_or_above():
            times = Time.objects.filter(ativo=True)
            if time_id:
                usuarios = perfil.get_visible_users().filter(perfil__time_id=time_id)
            else:
                usuarios = perfil.get_visible_users()
        elif perfil and perfil.is_lider_or_above():
            times = Time.objects.filter(pk=perfil.time_id, ativo=True)
            usuarios = perfil.get_visible_users()
        else:
            times = Time.objects.none()
            usuarios = perfil.get_visible_users() if perfil else User.objects.none()
        
        context = {
            'perfil': perfil,
            'total_hoje': total_hoje,
            'horas_trabalhadas': horas_str,
            'em_aberto': em_aberto,
            'sla_pct': sla_pct,
            'ultimos': ultimos,
            'times': times,
            'usuarios': usuarios,
            'daily_compliance': daily_compliance,
            'filtros': {
                'time': time_id,
                'usuario': usuario_id,
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'status': status,
                'prioridade': prioridade,
            },
            'status_choices': Apontamento.STATUS_CHOICES,
            'prioridade_choices': Apontamento.PRIORIDADE_CHOICES,
        }
        return render(request, 'dashboard.html', context)


# Apontamento Views
class ApontamentoListView(LoginRequiredMixin, ListView):
    model = Apontamento
    template_name = 'apontamentos/lista.html'
    context_object_name = 'apontamentos'
    paginate_by = None  # Sem paginação: o agrupamento por data requer o dia inteiro junto
    
    def get_queryset(self):
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        qs = Apontamento.objects.select_related('cliente', 'responsavel', 'equipamento').all()
        
        # Same permission logic as DashboardView
        if perfil and perfil.is_lider_or_above() and not perfil.is_gestor_or_above():
            qs = qs.filter(responsavel__perfil__time=perfil.time)
        elif not perfil or not perfil.is_gestor_or_above():
            qs = qs.filter(responsavel=self.request.user)
        
        # Filtros
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(ticket__icontains=q) |
                Q(cliente__corporation__icontains=q) |
                Q(projeto__icontains=q) |
                Q(solicitante__icontains=q)
            )
        
        status = self.request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)
            
        prioridade = self.request.GET.get('prioridade', '').strip()
        if prioridade:
            qs = qs.filter(prioridade=prioridade)
            
        data_inicio = self.request.GET.get('data_inicio', '').strip()
        if data_inicio:
            qs = qs.filter(data__gte=data_inicio)
            
        data_fim = self.request.GET.get('data_fim', '').strip()
        if data_fim:
            qs = qs.filter(data__lte=data_fim)
        
        return qs.order_by('-data', '-hora_inicial')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        context['perfil'] = perfil
        
        # Filter options for template
        context['status_choices'] = Apontamento.STATUS_CHOICES
        context['prioridade_choices'] = Apontamento.PRIORIDADE_CHOICES
        
        # Current filter values
        context['search'] = self.request.GET.get('q', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['prioridade_filter'] = self.request.GET.get('prioridade', '')
        context['data_inicio'] = self.request.GET.get('data_inicio', '')
        context['data_fim'] = self.request.GET.get('data_fim', '')
        
        # Time/Usuário filters for gestores
        if perfil and perfil.is_gestor_or_above():
            from .models import Time
            context['times'] = Time.objects.filter(ativo=True)
            context['time_filter'] = self.request.GET.get('time', '')
            if context['time_filter']:
                context['usuarios'] = User.objects.filter(
                    perfil__ativo=True, perfil__time_id=context['time_filter']
                ).select_related('perfil')
            else:
                context['usuarios'] = User.objects.filter(perfil__ativo=True).select_related('perfil')
            context['usuario_filter'] = self.request.GET.get('usuario', '')
        elif perfil and perfil.is_lider_or_above():
            context['usuarios'] = perfil.get_visible_users()
            context['usuario_filter'] = self.request.GET.get('usuario', '')

        # Agrupar apontamentos por data (já ordenados data DESC, hora DESC no queryset)
        from collections import OrderedDict
        apontamentos_por_data = OrderedDict()
        totais_por_data = {}
        for a in context['apontamentos']:
            apontamentos_por_data.setdefault(a.data, []).append(a)
        for data, lista in apontamentos_por_data.items():
            total_min = 0
            for a in lista:
                if a.tempo_total:
                    total_min += int(a.tempo_total.total_seconds() / 60)
            totais_por_data[data] = total_min
        context['apontamentos_por_data'] = apontamentos_por_data
        context['totais_por_data'] = totais_por_data

        return context


class ApontamentoCreateView(LoginRequiredMixin, CreateView):
    model = Apontamento
    form_class = ApontamentoForm
    template_name = 'apontamentos/form.html'
    success_url = reverse_lazy('semeq:apontamento_lista')
    
    @method_decorator(rate_limit(rate='20/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    @transaction.atomic
    def form_valid(self, form):
        # Bloqueia race condition: lock nas linhas do responsável+data antes de inserir
        data = form.cleaned_data
        if data.get('responsavel') and data.get('data'):
            Apontamento.objects.select_for_update().filter(
                responsavel=data['responsavel'],
                data=data['data'],
            ).exists()

        form.instance.criado_por = self.request.user
        # Respeita o responsável escolhido (admin/gestor pode selecionar outro usuário);
        # para colaborador, o form já força o próprio usuário (HiddenInput)
        resp = form.cleaned_data.get('responsavel')
        form.instance.responsavel = resp if resp else self.request.user
        messages.success(self.request, 'Apontamento criado com sucesso!')
        return super().form_valid(form)


class ApontamentoUpdateView(LoginRequiredMixin, UpdateView):
    model = Apontamento
    form_class = ApontamentoForm
    template_name = 'apontamentos/form.html'
    success_url = reverse_lazy('semeq:apontamento_lista')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_queryset(self):
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        qs = super().get_queryset()
        if perfil and perfil.is_gestor_or_above():
            return qs
        elif perfil and perfil.is_lider_or_above():
            return qs.filter(responsavel__perfil__time=perfil.time)
        return qs.filter(responsavel=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Apontamento atualizado com sucesso!')
        return super().form_valid(form)


class ApontamentoDeleteView(LoginRequiredMixin, DeleteView):
    model = Apontamento
    template_name = 'apontamentos/confirm_delete.html'
    success_url = reverse_lazy('semeq:apontamento_lista')
    
    def get_queryset(self):
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        qs = super().get_queryset()
        if perfil and perfil.is_gestor_or_above():
            return qs
        elif perfil and perfil.is_lider_or_above():
            return qs.filter(responsavel__perfil__time=perfil.time)
        return qs.filter(responsavel=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Apontamento excluído com sucesso!')
        return super().delete(request, *args, **kwargs)


class ApontamentoDetailView(LoginRequiredMixin, DetailView):
    model = Apontamento
    template_name = 'apontamentos/detail.html'
    context_object_name = 'apontamento'
    
    def get_queryset(self):
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        qs = super().get_queryset().select_related('cliente', 'responsavel', 'equipamento', 'criado_por')
        if perfil and perfil.is_gestor_or_above():
            return qs
        elif perfil and perfil.is_lider_or_above():
            return qs.filter(responsavel__perfil__time=perfil.time)
        return qs.filter(responsavel=self.request.user)


class ApontamentoStatusView(LoginRequiredMixin, View):
    """
    Altera o status de um apontamento via AJAX (POST).
    Usado nas telas de lista (/apontamentos/), dashboard e detalhe.
    """
    @method_decorator(rate_limit(rate='30/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_apontamento(self, request, pk):
        perfil = request.user.perfil if hasattr(request.user, 'perfil') else None
        ap = get_object_or_404(Apontamento, pk=pk)
        # Mesma lógica de permissão das demais views de apontamento
        if perfil and perfil.is_gestor_or_above():
            return ap
        elif perfil and perfil.is_lider_or_above():
            if ap.responsavel.perfil.time_id == perfil.time_id:
                return ap
        else:
            if ap.responsavel_id == request.user.id:
                return ap
        return None

    def post(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Requisição inválida.'}, status=400)

        ap = self.get_apontamento(request, kwargs.get('pk'))
        if ap is None:
            return JsonResponse({'success': False, 'message': 'Você não tem permissão para alterar este apontamento.'}, status=403)

        novo_status = request.POST.get('status', '').strip()
        status_validos = {key for key, _ in Apontamento.STATUS_CHOICES}
        if novo_status not in status_validos:
            return JsonResponse({'success': False, 'message': 'Status inválido.'}, status=400)

        ap.status = novo_status
        ap.save()

        return JsonResponse({
            'success': True,
            'message': 'Status atualizado com sucesso!',
            'status': ap.get_status_display(),
        })


class ApontamentoExportView(LoginRequiredMixin, View):
    def get(self, request):
        formato = request.GET.get('formato', 'csv')
        perfil = request.user.perfil if hasattr(request.user, 'perfil') else None
        
        qs = Apontamento.objects.select_related('cliente', 'responsavel', 'equipamento').all()
        
        if perfil and perfil.is_lider_or_above() and not perfil.is_gestor_or_above():
            qs = qs.filter(responsavel__perfil__time=perfil.time)
        elif not perfil or not perfil.is_gestor_or_above():
            qs = qs.filter(responsavel=request.user)
        
        if formato == 'xlsx':
            return self.export_xlsx(qs)
        return self.export_csv(qs)
    
    def export_csv(self, qs):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="apontamentos_{date.today()}.csv"'
        response.write('\ufeff'.encode('utf-8'))  # BOM para Excel
        
        writer = csv.writer(response, delimiter=';')
        writer.writerow([
            'Ticket', 'Cliente', 'Projeto', 'Solicitante', 'Equipamento',
            'Prioridade', 'Equipe', 'Responsável', 'Atividade', 'Tipo Problema',
            'Status', 'Data', 'Hora Inicial', 'Hora Final', 'Tempo Total',
            'GW no Ar', 'Desvio', 'Descrição'
        ])
        
        for a in qs:
            writer.writerow([
                a.ticket, f"{a.cliente.corporation} - {a.cliente.plant}", a.projeto,
                a.solicitante, str(a.equipamento) if a.equipamento else '',
                a.get_prioridade_display(), a.get_equipe_display(),
                a.responsavel.get_full_name() or a.responsavel.username,
                a.get_atividade_display(), a.get_tipo_problema_display(),
                a.get_status_display(), a.data.strftime('%d/%m/%Y'),
                a.hora_inicial.strftime('%H:%M'), a.hora_final.strftime('%H:%M'),
                str(a.tempo_total) if a.tempo_total else '',
                'Sim' if a.gw_ar else 'Não', a.get_desvio_display(), a.descricao
            ])
        return response
    
    def export_xlsx(self, qs):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Apontamentos'
        
        headers = [
            'Ticket', 'Cliente', 'Projeto', 'Solicitante', 'Equipamento',
            'Prioridade', 'Equipe', 'Responsável', 'Atividade', 'Tipo Problema',
            'Status', 'Data', 'Hora Inicial', 'Hora Final', 'Tempo Total',
            'GW no Ar', 'Desvio', 'Descrição'
        ]
        ws.append(headers)
        
        for a in qs:
            ws.append([
                a.ticket, f"{a.cliente.corporation} - {a.cliente.plant}", a.projeto,
                a.solicitante, str(a.equipamento) if a.equipamento else '',
                a.get_prioridade_display(), a.get_equipe_display(),
                a.responsavel.get_full_name() or a.responsavel.username,
                a.get_atividade_display(), a.get_tipo_problema_display(),
                a.get_status_display(), a.data.strftime('%d/%m/%Y'),
                a.hora_inicial.strftime('%H:%M'), a.hora_final.strftime('%H:%M'),
                str(a.tempo_total) if a.tempo_total else '',
                'Sim' if a.gw_ar else 'Não', a.get_desvio_display(), a.descricao
            ])
        
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="apontamentos_{date.today()}.xlsx"'
        wb.save(response)
        return response


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
                Q(plant__icontains=q) |
                Q(corporation_id__icontains=q) |
                Q(plant_id__icontains=q) |
                Q(city__icontains=q)
            )
        
        # Specific field filters
        corporation_id = self.request.GET.get('corporation_id', '').strip()
        if corporation_id:
            qs = qs.filter(corporation_id=corporation_id)
        
        corporation = self.request.GET.get('corporation', '').strip()
        if corporation:
            qs = qs.filter(corporation__icontains=corporation)
        
        plant_id = self.request.GET.get('plant_id', '').strip()
        if plant_id:
            qs = qs.filter(plant_id=plant_id)
        
        plant = self.request.GET.get('plant', '').strip()
        if plant:
            qs = qs.filter(plant__icontains=plant)
        
        city = self.request.GET.get('city', '').strip()
        if city:
            qs = qs.filter(city__icontains=city)
        
        state = self.request.GET.get('state', '').strip()
        if state:
            qs = qs.filter(state_province=state)
        
        country = self.request.GET.get('country', '').strip()
        if country:
            qs = qs.filter(country=country)
        
        # Status filter (default to active only)
        ativo = self.request.GET.get('ativo', 'true')
        if ativo == 'true':
            qs = qs.filter(ativo=True)
        elif ativo == 'false':
            qs = qs.filter(ativo=False)
        # ativo == 'all' or empty -> no filter
        
        return qs.order_by('corporation', 'plant')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pass current filter values to template
        context['filters'] = {
            'q': self.request.GET.get('q', ''),
            'corporation_id': self.request.GET.get('corporation_id', ''),
            'corporation': self.request.GET.get('corporation', ''),
            'plant_id': self.request.GET.get('plant_id', ''),
            'plant': self.request.GET.get('plant', ''),
            'city': self.request.GET.get('city', ''),
            'state': self.request.GET.get('state', ''),
            'country': self.request.GET.get('country', ''),
            'ativo': self.request.GET.get('ativo', 'true'),
        }
        
        # Get distinct values for dropdowns (from base queryset without filters)
        base_qs = Cliente.objects.all()
        
        # Static lists for dropdowns
        context['states'] = list(base_qs.exclude(state_province='').values_list('state_province', flat=True).distinct().order_by('state_province'))
        context['countries'] = list(base_qs.exclude(country='').values_list('country', flat=True).distinct().order_by('country'))
        
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
    template_name = 'clientes/form.html'
    success_url = reverse_lazy('semeq:cliente_lista')
    
    def form_valid(self, form):
        messages.success(self.request, 'Cliente criado com sucesso!')
        return super().form_valid(form)


class ClienteUpdateView(ClientePermissionMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/form.html'
    success_url = reverse_lazy('semeq:cliente_lista')
    
    def form_valid(self, form):
        messages.success(self.request, 'Cliente atualizado com sucesso!')
        return super().form_valid(form)


class ClienteDeleteView(ClientePermissionMixin, DeleteView):
    model = Cliente
    template_name = 'clientes/confirm_delete.html'
    success_url = reverse_lazy('semeq:cliente_lista')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Cliente excluído com sucesso!')
        return super().delete(request, *args, **kwargs)


class ClienteDeleteAllView(ClientePermissionMixin, View):
    """Delete ALL clientes + cascade (equipamentos, apontamentos). Admin only."""
    
    def dispatch(self, request, *args, **kwargs):
        perfil = request.user.perfil if hasattr(request.user, 'perfil') else None
        if not (request.user.is_superuser or (perfil and perfil.is_admin())):
            messages.error(request, 'Acesso negado. Apenas administradores.')
            return redirect('semeq:cliente_lista')
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        from user.models import Apontamento, Equipamento, Cliente
        
        # Count for confirmation page
        clientes_count = Cliente.objects.count()
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
        
        # Count before deletion
        apontamentos_count = Apontamento.objects.count()
        equipamentos_count = Equipamento.objects.count()
        clientes_count = Cliente.objects.count()
        
        # Delete in correct order (FK PROTECT)
        Apontamento.objects.all().delete()
        Equipamento.objects.all().delete()
        Cliente.objects.all().delete()
        
        messages.success(
            request, 
            f'Exclusão completa: {clientes_count} clientes, {equipamentos_count} equipamentos, '
            f'{apontamentos_count} apontamentos removidos.'
        )
        return redirect('semeq:cliente_lista')


class ClienteImportView(ClientePermissionMixin, View):
    @method_decorator(rate_limit(rate='5/m', key='user_or_ip', method='POST', block=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = ClienteImportForm()
        return render(request, 'clientes/importar.html', {'form': form})

    @staticmethod
    def _fix_encoding(value):
        """
        Corrige encoding legado (latin-1/cp1252 armazenado como bytes).
        Converte C1 controls (0x80-0x9F) para equivalentes Unicode via cp1252.
        """
        if not value:
            return value
        try:
            fixed = value.encode('latin-1').decode('cp1252')
            return fixed if fixed != value else value
        except (UnicodeEncodeError, UnicodeDecodeError):
            return value
    
    def _parse_file(self, arquivo, ext):
        """Parse Excel or CSV file, return (headers, rows)"""
        if ext in ['xlsx', 'xls']:
            df = openpyxl.load_workbook(arquivo, read_only=True)
            sheet = df.active
            all_rows = list(sheet.iter_rows(values_only=True))
            if not all_rows:
                return [], []
            headers = [str(h or '').strip() for h in all_rows[0]]
            rows = [[str(c or '').strip() for c in r] for r in all_rows[1:]]
            return headers, rows
        else:
            import io
            content = arquivo.read()
            # Handle BOM (UTF-8)
            if content.startswith(b'\xef\xbb\xbf'):
                content = content[3:]
                content = content.decode('utf-8')
            else:
                # Detectar encoding: tenta UTF-8, senão CP1252/Latin-1 (arquivos Excel legados)
                try:
                    content = content.decode('utf-8')
                except (UnicodeDecodeError, UnicodeError):
                    content = content.decode('cp1252')
            
            # Auto-detect delimiter
            sample = content[:1024]
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample, delimiters=',;\t')
                delimiter = dialect.delimiter
            except:
                delimiter = ';' if ';' in sample else ','
            
            reader = csv.reader(io.StringIO(content), delimiter=delimiter)
            all_rows = list(reader)
            if not all_rows:
                return [], []
            headers = [str(h or '').strip() for h in all_rows[0]]
            rows = [[str(c or '').strip() for c in r] for r in all_rows[1:]]
            return headers, rows
    
    def _normalize_row(self, row, headers):
        """Map row values by header name (case-insensitive)"""
        row_dict = {}
        header_lower = {h.lower(): i for i, h in enumerate(headers)}
        for key in ['corporation_id', 'corporation', 'plant_id', 'plant', 'unat', 
                    'city', 'state_province', 'country', 'region', 'business', 'zone']:
            idx = header_lower.get(key.lower())
            row_dict[key] = row[idx] if idx is not None and idx < len(row) else ''
        return row_dict
    
    def post(self, request):
        confirmar = request.POST.get('confirmar')
        
        if confirmar:
            # Step 2: Confirm import from session data
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
                    corp_id = row_data.get('corporation_id', '')
                    corp = self._fix_encoding(row_data.get('corporation', ''))
                    plant_id = row_data.get('plant_id', '')
                    plant = self._fix_encoding(row_data.get('plant', ''))
                    unat = self._fix_encoding(row_data.get('unat', ''))
                    city = self._fix_encoding(row_data.get('city', ''))
                    state = self._fix_encoding(row_data.get('state_province', ''))
                    country = self._fix_encoding(row_data.get('country', ''))
                    region = self._fix_encoding(row_data.get('region', ''))
                    business = self._fix_encoding(row_data.get('business', ''))
                    zone = self._fix_encoding(row_data.get('zone', ''))
                    
                    if not corp_id or not plant_id:
                        erros.append(f'Linha {i}: corporation_id e plant_id são obrigatórios')
                        continue
                    
                    obj, created = Cliente.objects.update_or_create(
                        corporation_id=corp_id,
                        plant_id=plant_id,
                        defaults={
                            'corporation': corp,
                            'plant': plant,
                            'unat': unat,
                            'city': city,
                            'state_province': state,
                            'country': country,
                            'region': region,
                            'business': business,
                            'zone': zone,
                            'ativo': True,
                        }
                    )
                    if created:
                        criados += 1
                    else:
                        atualizados += 1
                except Exception as e:
                    erros.append(f'Linha {i}: {str(e)}')
            
            messages.success(request, f'Importação concluída: {criados} criados, {atualizados} atualizados.')
            if erros:
                messages.warning(request, f'Erros: {"; ".join(erros[:5])}' + ('...' if len(erros) > 5 else ''))
            return redirect('semeq:cliente_lista')
        
        # Step 1: Upload and show preview
        form = ClienteImportForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = form.cleaned_data['arquivo']
            atualizar = form.cleaned_data['atualizar_existentes']
            
            ext = arquivo.name.lower().split('.')[-1]
            headers, rows = self._parse_file(arquivo, ext)
            
            if not headers:
                messages.error(request, 'Arquivo vazio ou inválido.')
                return render(request, 'clientes/importar.html', {'form': form})
            
            # Normalize rows to dict by header
            normalized_rows = [self._normalize_row(r, headers) for r in rows]
            
            # Store in session for confirmation step
            request.session['cliente_import_data'] = {
                'atualizar': atualizar,
                'rows': normalized_rows,
                'ext': ext,
            }
            
            # Show preview (first 5 rows)
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


class ClienteExportView(ClientePermissionMixin, View):
    def get(self, request):
        qs = Cliente.objects.filter(ativo=True).order_by('corporation', 'plant')
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="clientes_{date.today()}.csv"'
        response.write('\ufeff'.encode('utf-8'))
        
        writer = csv.writer(response, delimiter=';')
        writer.writerow([
            'CORPORATION_ID', 'CORPORATION', 'PLANT_ID', 'PLANT', 'UNAT',
            'CITY', 'STATE_PROVINCE', 'COUNTRY', 'REGION', 'BUSINESS', 'ZONE'
        ])
        
        for c in qs:
            writer.writerow([
                c.corporation_id, c.corporation, c.plant_id, c.plant, c.unat,
                c.city, c.state_province, c.country, c.region, c.business, c.zone
            ])
        return response


class ClienteFilterOptionsView(ClientePermissionMixin, View):
    """API endpoint for cascading filter options."""
    
    def get(self, request):
        field = request.GET.get('field', '')
        parent_field = request.GET.get('parent_field', '')
        parent_value = request.GET.get('parent_value', '')
        
        qs = Cliente.objects.filter(ativo=True)
        
        if field == 'corporacoes':
            # All corporations
            data = list(qs.values('corporation_id', 'corporation').distinct().order_by('corporation'))
            return JsonResponse({'options': data})
        
        elif field == 'plantas':
            # Plants, optionally filtered by corporation_id
            if parent_field == 'corporation_id' and parent_value:
                qs = qs.filter(corporation_id=parent_value)
            data = list(qs.values('plant_id', 'plant').distinct().order_by('plant')[:200])
            return JsonResponse({'options': data})
        
        elif field == 'cidades':
            # Cities, optionally filtered by state
            if parent_field == 'state' and parent_value:
                qs = qs.filter(state_province=parent_value)
            data = list(qs.exclude(city='').values_list('city', flat=True).distinct().order_by('city')[:200])
            return JsonResponse({'options': data})
        
        elif field == 'estados':
            # All states
            data = list(qs.exclude(state_province='').values_list('state_province', flat=True).distinct().order_by('state_province'))
            return JsonResponse({'options': data})
        
        elif field == 'paises':
            # All countries
            data = list(qs.exclude(country='').values_list('country', flat=True).distinct().order_by('country'))
            return JsonResponse({'options': data})
        
        elif field == 'regioes':
            # All regions
            data = list(qs.exclude(region='').values_list('region', flat=True).distinct().order_by('region'))
            return JsonResponse({'options': data})
        
        elif field == 'negocios':
            # All businesses
            data = list(qs.exclude(business='').values_list('business', flat=True).distinct().order_by('business'))
            return JsonResponse({'options': data})
        
        # Default: return all
        corporacoes = list(qs.values('corporation_id', 'corporation').distinct().order_by('corporation'))
        plantas = list(qs.values('plant_id', 'plant').distinct().order_by('plant')[:100])
        return JsonResponse({'corporacoes': corporacoes, 'plantas': plantas})


class ClienteAutocompleteView(LoginRequiredMixin, View):
    """Autocomplete search para o formulário de apontamento (qualquer usuário logado).
    O form de criação exige que colaboradores/líderes possam selecionar cliente/planta."""
    
    def get(self, request):
        q = request.GET.get('q', '').strip()
        qs = Cliente.objects.filter(ativo=True)
        if q:
            qs = qs.filter(
                Q(corporation__icontains=q) |
                Q(plant__icontains=q) |
                Q(corporation_id__icontains=q) |
                Q(plant_id__icontains=q) |
                Q(city__icontains=q)
            )
        data = list(qs.values('pk', 'corporation_id', 'corporation', 'plant_id', 'plant', 'city')[:50])
        return JsonResponse({'results': data})


class EquipamentoAutocompleteView(LoginRequiredMixin, View):
    """Autocomplete search for equipamentos."""
    
    def get(self, request):
        q = request.GET.get('q', '').strip()
        qs = Equipamento.objects.filter(ativo=True).select_related('cliente')
        if q:
            qs = qs.filter(
                Q(numero_serie__icontains=q) |
                Q(modelo__icontains=q) |
                Q(tipo__icontains=q) |
                Q(cliente__corporation__icontains=q) |
                Q(cliente__plant__icontains=q)
            )
        data = list(qs.values(
            'pk', 'numero_serie', 'modelo', 'tipo',
            corporation=F('cliente__corporation'),
            plant=F('cliente__plant'),
        )[:50])
        return JsonResponse({'results': data})


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
        qs = User.objects.select_related('perfil', 'perfil__time').filter(is_active=True)
        
        if perfil and perfil.is_gestor_or_above():
            qs = qs.filter(perfil__ativo=True)
        elif perfil and perfil.is_lider_or_above():
            qs = qs.filter(perfil__ativo=True, perfil__time=perfil.time)
        else:
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
        
        time = self.request.GET.get('time', '').strip()
        if time:
            qs = qs.filter(perfil__time_id=time)
        
        return qs.order_by('username')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = PerfilUsuario.ROLE_CHOICES
        context['times'] = Time.objects.filter(ativo=True)
        context['role_filter'] = self.request.GET.get('role', '')
        context['time_filter'] = self.request.GET.get('time', '')
        context['search'] = self.request.GET.get('q', '')
        return context


class UsuarioCreateView(UsuarioPermissionMixin, CreateView):
    form_class = UsuarioForm
    template_name = 'usuarios/form.html'
    success_url = reverse_lazy('semeq:usuario_lista')
    
    def form_valid(self, form):
        messages.success(self.request, 'Usuário criado com sucesso!')
        return super().form_valid(form)


class UsuarioUpdateView(UsuarioPermissionMixin, UpdateView):
    model = User
    form_class = UsuarioUpdateForm
    template_name = 'usuarios/form.html'
    success_url = reverse_lazy('semeq:usuario_lista')
    
    def get_queryset(self):
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        qs = User.objects.select_related('perfil', 'perfil__time').filter(is_active=True)
        
        if perfil and perfil.is_gestor_or_above():
            qs = qs.filter(perfil__ativo=True)
            # Gestor não pode editar admins/superusers (evita elevação de privilégio)
            if not (self.request.user.is_superuser or perfil.is_admin()):
                qs = qs.exclude(is_superuser=True).exclude(perfil__role='admin')
        elif perfil and perfil.is_lider_or_above():
            qs = qs.filter(perfil__ativo=True, perfil__time=perfil.time)
        return qs.filter(id=self.request.user.id)
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        perfil = getattr(self.request.user, 'perfil', None)
        # Impede gestor/não-admin de editar usuários de hierarquia maior
        if perfil and not perfil.is_admin() and obj.is_superuser:
            raise PermissionDenied('Você não tem permissão para editar este usuário.')
        return obj
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Usuário atualizado com sucesso!')
        return super().form_valid(form)


class UsuarioDeleteView(UsuarioPermissionMixin, DeleteView):
    model = PerfilUsuario
    template_name = 'usuarios/confirm_delete.html'
    success_url = reverse_lazy('semeq:usuario_lista')
    
    def get_queryset(self):
        perfil = self.request.user.perfil if hasattr(self.request.user, 'perfil') else None
        qs = PerfilUsuario.objects.select_related('user', 'time').filter(ativo=True)
        
        if perfil and perfil.is_gestor_or_above():
            return qs
        elif perfil and perfil.is_lider_or_above():
            return qs.filter(time=perfil.time)
        return qs.filter(user=self.request.user)
    
    def get_object(self):
        obj = get_object_or_404(PerfilUsuario, user__pk=self.kwargs['pk'])
        # Impede auto-exclusão
        if obj.user == self.request.user:
            messages.error(self.request, 'Você não pode excluir seu próprio usuário.')
            raise PermissionDenied
        return obj
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Usuário excluído com sucesso!')
        return super().delete(request, *args, **kwargs)


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
        qs = Equipamento.objects.select_related('cliente').all()
        filters = {
            'equipamento_id': self.request.GET.get('equipamento_id', '').strip(),
            'cliente': self.request.GET.get('cliente', '').strip(),
            'tipo': self.request.GET.get('tipo', '').strip(),
            'numero_serie': self.request.GET.get('numero_serie', '').strip(),
            'modelo': self.request.GET.get('modelo', '').strip(),
            'ativo': self.request.GET.get('ativo', ''),
        }
        if filters['equipamento_id']:
            qs = qs.filter(equipamento_id__icontains=filters['equipamento_id'])
        if filters['cliente']:
            qs = qs.filter(
                Q(cliente__corporation__icontains=filters['cliente']) |
                Q(cliente__plant__icontains=filters['cliente'])
            )
        if filters['tipo']:
            qs = qs.filter(tipo=filters['tipo'])
        if filters['numero_serie']:
            qs = qs.filter(numero_serie__icontains=filters['numero_serie'])
        if filters['modelo']:
            qs = qs.filter(modelo__icontains=filters['modelo'])
        if filters['ativo'] == 'true':
            qs = qs.filter(ativo=True)
        elif filters['ativo'] == 'false':
            qs = qs.filter(ativo=False)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = {
            'equipamento_id': self.request.GET.get('equipamento_id', ''),
            'cliente': self.request.GET.get('cliente', ''),
            'tipo': self.request.GET.get('tipo', ''),
            'numero_serie': self.request.GET.get('numero_serie', ''),
            'modelo': self.request.GET.get('modelo', ''),
            'ativo': self.request.GET.get('ativo', ''),
        }
        context['tipo_choices'] = Equipamento.TIPO_CHOICES
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filter_params'] = params.urlencode()
        return context


class EquipamentoCreateView(EquipamentoPermissionMixin, CreateView):
    model = Equipamento
    form_class = EquipamentoForm
    template_name = 'equipamentos/form.html'
    success_url = reverse_lazy('semeq:equipamento_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Equipamento criado com sucesso!')
        return super().form_valid(form)


class EquipamentoUpdateView(EquipamentoPermissionMixin, UpdateView):
    model = Equipamento
    form_class = EquipamentoForm
    template_name = 'equipamentos/form.html'
    success_url = reverse_lazy('semeq:equipamento_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Equipamento atualizado com sucesso!')
        return super().form_valid(form)


class EquipamentoDeleteView(EquipamentoPermissionMixin, DeleteView):
    model = Equipamento
    template_name = 'equipamentos/confirm_delete.html'
    success_url = reverse_lazy('semeq:equipamento_lista')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Equipamento excluído com sucesso!')
        return super().delete(request, *args, **kwargs)
