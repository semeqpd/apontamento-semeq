from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'semeq'

urlpatterns = [
    path('', views.HomeView, name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    # Apontamento
    path('apontamentos/', views.ApontamentoListView.as_view(), name='apontamento_lista'),
    path('apontamentos/novo/', views.ApontamentoCreateView.as_view(), name='apontamento_novo'),
    path('apontamentos/<int:pk>/', views.ApontamentoDetailView.as_view(), name='apontamento_detalhe'),
    path('apontamentos/<int:pk>/editar/', views.ApontamentoUpdateView.as_view(), name='apontamento_editar'),
    path('apontamentos/<int:pk>/status/', views.ApontamentoStatusView.as_view(), name='apontamento_mudar_status'),
    path('apontamentos/<int:pk>/excluir/', views.ApontamentoDeleteView.as_view(), name='apontamento_excluir'),
    path('apontamentos/exportar/', views.ApontamentoExportView.as_view(), name='apontamento_exportar'),

    # Cliente
    path('clientes/', views.ClienteListView.as_view(), name='cliente_lista'),
    path('clientes/novo/', views.ClienteCreateView.as_view(), name='cliente_novo'),
    path('clientes/<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_editar'),
    path('clientes/<int:pk>/excluir/', views.ClienteDeleteView.as_view(), name='cliente_excluir'),
    path('clientes/excluir-todos/', views.ClienteDeleteAllView.as_view(), name='cliente_excluir_todos'),
    path('clientes/importar/', views.ClienteImportView.as_view(), name='cliente_importar'),
    path('clientes/importar/processar/', views.ClienteImportProcessView.as_view(), name='cliente_importar_processo'),
    path('clientes/exportar/', views.ClienteExportView.as_view(), name='cliente_exportar'),
    path('clientes/filtro-opcoes/', views.ClienteFilterOptionsView.as_view(), name='cliente_filtro_opcoes'),
    path('clientes/autocomplete/', views.ClienteAutocompleteView.as_view(), name='cliente_autocomplete'),
    path('clientes/buscar/', views.ClienteBuscaView.as_view(), name='cliente_buscar'),
    path('clientes/autocomplete/corporacoes/', views.ClienteCorporacoesAutocompleteView.as_view(), name='cliente_autocomplete_corporacoes'),
    path('clientes/autocomplete/plantas/', views.ClientePlantasAutocompleteView.as_view(), name='cliente_autocomplete_plantas'),
    path('equipamentos/autocomplete/', views.EquipamentoAutocompleteView.as_view(), name='equipamento_autocomplete'),

    # Usuario
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_lista'),
    path('usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuario_novo'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_editar'),
    path('usuarios/<int:pk>/excluir/', views.UsuarioDeleteView.as_view(), name='usuario_excluir'),

    # Configurações
    path('configuracoes/', views.ConfiguracoesView.as_view(), name='configuracoes'),
    path('configuracoes/tema/', views.ConfiguracoesTemaView.as_view(), name='configuracoes_tema'),

    # Equipamento
    path('equipamentos/', views.EquipamentoListView.as_view(), name='equipamento_lista'),
    path('equipamentos/novo/', views.EquipamentoCreateView.as_view(), name='equipamento_novo'),
    path('equipamentos/<int:pk>/editar/', views.EquipamentoUpdateView.as_view(), name='equipamento_editar'),
    path('equipamentos/<int:pk>/excluir/', views.EquipamentoDeleteView.as_view(), name='equipamento_excluir'),

    # Times - DEACTIVATED (modo construção)
    # DEACTIVATED: path('times/', views.TimeListView.as_view(), name='time_lista'),
    # DEACTIVATED: path('times/novo/', views.TimeCreateView.as_view(), name='time_novo'),
    # DEACTIVATED: path('times/<int:pk>/editar/', views.TimeUpdateView.as_view(), name='time_editar'),
    # DEACTIVATED: path('times/<int:pk>/excluir/', views.TimeDeleteView.as_view(), name='time_excluir'),


    # Auth - Login por email
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(next_page='semeq:login'), name='logout'),
    path('senha/alterar/', auth_views.PasswordChangeView.as_view(
        template_name='registration/password_change.html',
        success_url='/'
    ), name='password_change'),
    
    # Cadastro Público (domínios permitidos)
    path('cadastro/', views.PublicRegistrationView.as_view(), name='register'),
    path('cadastro/sucesso/', views.PublicRegistrationDoneView.as_view(), name='register_done'),
    
    # Verificação de Email
    path('verificar-email/<uuid:token>/', views.EmailVerificationView.as_view(), name='email_verificar'),
    
    # Password Reset
    path('senha/esqueci/', views.SemeqPasswordResetView.as_view(), name='password_reset'),
    path('senha/esqueci/enviado/', views.SemeqPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('senha/redefinir/<uidb64>/<token>/', views.SemeqPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('senha/redefinido/', views.SemeqPasswordResetCompleteView.as_view(), name='password_reset_complete'),

]