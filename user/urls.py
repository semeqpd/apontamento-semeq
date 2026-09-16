from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from . import views
from .forms import SemeqPasswordResetForm, SemeqPasswordChangeForm

app_name = 'semeq'

urlpatterns = [
    path('', views.HomeView, name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    # Apontamento (novo modelo: Atendimento)
    path('apontamentos/', views.ApontamentoListView.as_view(), name='apontamento_lista'),
    path('apontamentos/novo/', views.ApontamentoCreateView.as_view(), name='apontamento_novo'),
    path('apontamentos/<int:pk>/', views.ApontamentoDetailView.as_view(), name='apontamento_detalhe'),
    path('apontamentos/<int:pk>/editar/', views.ApontamentoUpdateView.as_view(), name='apontamento_editar'),
    path('apontamentos/<int:pk>/status/', views.ApontamentoStatusView.as_view(), name='apontamento_mudar_status'),
    path('apontamentos/<int:pk>/alterar-status/', views.alterar_status_apontamento, name='apontamento_alterar_status'),
    path('apontamentos/<int:pk>/tipo-problema/', views.ApontamentoTipoProblemaView.as_view(), name='apontamento_mudar_tipo_problema'),
    path('apontamentos/<int:pk>/excluir/', views.excluir_apontamento, name='apontamento_excluir'),
    path('apontamentos/exportar/', views.ApontamentoExportView.as_view(), name='apontamento_exportar'),

    # Apontamento Tempo (apontamentos)
    path('apontamentos/<int:apontamento_pk>/apontamento/novo/', views.ApontamentoTempoCreateView.as_view(), name='apontamentotempo_novo'),
    path('apontamentos/<int:apontamento_pk>/apontamento/<int:pk>/editar/', views.ApontamentoTempoUpdateView.as_view(), name='apontamentotempo_editar'),
    path('apontamentos/<int:apontamento_pk>/apontamento/<int:pk>/excluir/', views.ApontamentoTempoDeleteView.as_view(), name='apontamentotempo_excluir'),

    # Apontamento Tempo (novo modelo - atendimentos)
    path('atendimentos/', views.ApontamentoListView.as_view(), name='atendimento_lista'),
    path('apontamentos/novo/', views.ApontamentoCreateView.as_view(), name='atendimento_novo'),
    path('apontamentos/<int:pk>/', views.ApontamentoDetailView.as_view(), name='atendimento_detalhe'),
    path('apontamentos/<int:pk>/editar/', views.ApontamentoUpdateView.as_view(), name='atendimento_editar'),
    path('apontamentos/<int:pk>/excluir/', views.excluir_apontamento, name='atendimento_excluir'),
    path('atendimentos/<int:apontamento_pk>/apontamento/novo/', views.ApontamentoTempoCreateView.as_view(), name='apontamentotempo_novo'),
    path('atendimentos/<int:apontamento_pk>/apontamento/<int:pk>/editar/', views.ApontamentoTempoUpdateView.as_view(), name='apontamentotempo_editar'),
    path('atendimentos/<int:apontamento_pk>/apontamento/<int:pk>/excluir/', views.ApontamentoTempoDeleteView.as_view(), name='apontamentotempo_excluir'),

    # Cadastros - Novas URLs organizadas sob /cadastros/
    path('cadastros/', views.CadastrosUnificadaView.as_view(), name='cadastros_unificada'),
    
    # Principais (4 abas da página principal)
    path('cadastros/clientes/', views.CadastroClienteView.as_view(), name='cadastro_clientes'),
    path('cadastros/usuarios/', views.CadastroUsuarioView.as_view(), name='cadastro_usuarios'),
    path('cadastros/equipes/', views.CadastroEquipeView.as_view(), name='cadastro_equipes'),
    path('cadastros/equipamentos/', views.CadastroEquipamentoView.as_view(), name='cadastro_equipamentos'),
    
    # Auxiliares
    path('cadastros/status/', views.CadastroStatusView.as_view(), name='cadastro_status'),
    path('cadastros/atividades/', views.CadastroAtividadeView.as_view(), name='cadastro_atividades'),
    path('cadastros/prioridades/', views.CadastroPrioridadeView.as_view(), name='cadastro_prioridades'),
    path('cadastros/tipoproblemas/', views.CadastroTipoProblemaView.as_view(), name='cadastro_tipoproblemas'),
    path('cadastros/projetos/', views.CadastroProjetoView.as_view(), name='cadastro_projetos'),
    path('cadastros/solicitantes/', views.CadastroSolicitanteView.as_view(), name='cadastro_solicitantes'),

    # CRUD Clientes
    path('cadastros/clientes/novo/', views.ClienteCreateView.as_view(), name='cliente_novo'),
    path('cadastros/clientes/<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_editar'),
    path('cadastros/clientes/<int:pk>/excluir/', views.ClienteDeleteView.as_view(), name='cliente_excluir'),
    path('cadastros/clientes/excluir-todos/', views.ClienteDeleteAllView.as_view(), name='cliente_excluir_todos'),
    path('cadastros/clientes/importar/', views.ClienteImportView.as_view(), name='cliente_importar'),
    path('cadastros/clientes/importar/processar/', views.ClienteImportProcessView.as_view(), name='cliente_importar_processo'),
    path('cadastros/clientes/filtro-opcoes/', views.ClienteFilterOptionsView.as_view(), name='cliente_filtro_opcoes'),
    path('cadastros/clientes/autocomplete/', views.ClienteAutocompleteView.as_view(), name='cliente_autocomplete'),
    path('cadastros/clientes/buscar/', views.ClienteBuscaView.as_view(), name='cliente_buscar'),
    path('buscar-clientes/', views.buscar_clientes, name='buscar_clientes'),
    path('buscar-corporacoes/', views.buscar_corporacoes, name='buscar_corporacoes'),
    path('buscar-plantas/', views.buscar_plantas, name='buscar_plantas'),
    path('buscar-cliente-detalhe/', views.buscar_cliente_detalhe, name='buscar_cliente_detalhe'),
    path('cadastros/clientes/autocomplete/corporacoes/', views.ClienteCorporacoesAutocompleteView.as_view(), name='cliente_autocomplete_corporacoes'),
    path('cadastros/clientes/autocomplete/plantas/', views.ClientePlantasAutocompleteView.as_view(), name='cliente_autocomplete_plantas'),

    # CRUD Usuarios
    path('cadastros/usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuario_novo'),
    path('cadastros/usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_editar'),
    path('cadastros/usuarios/<int:pk>/excluir/', views.UsuarioDeleteView.as_view(), name='usuario_excluir'),

    # CRUD Equipes
    path('cadastros/equipes/novo/', views.EquipeCreateView.as_view(), name='equipe_novo'),
    path('cadastros/equipes/<int:pk>/editar/', views.EquipeUpdateView.as_view(), name='equipe_editar'),
    path('cadastros/equipes/<int:pk>/excluir/', views.EquipeDeleteView.as_view(), name='equipe_excluir'),

    # CRUD Equipamentos
    path('cadastros/equipamentos/novo/', views.EquipamentoCreateView.as_view(), name='equipamento_novo'),
    path('cadastros/equipamentos/<int:pk>/editar/', views.EquipamentoUpdateView.as_view(), name='equipamento_editar'),
    path('cadastros/equipamentos/<int:pk>/excluir/', views.EquipamentoDeleteView.as_view(), name='equipamento_excluir'),
    path('equipamentos/autocomplete/', views.EquipamentoAutocompleteView.as_view(), name='equipamento_autocomplete'),

    # CRUD Status
    path('cadastros/status/novo/', views.StatusCreateView.as_view(), name='status_novo'),
    path('cadastros/status/<int:pk>/editar/', views.StatusUpdateView.as_view(), name='status_editar'),
    path('cadastros/status/<int:pk>/excluir/', views.StatusDeleteView.as_view(), name='status_excluir'),
    
    # CRUD Atividade
    path('cadastros/atividades/novo/', views.AtividadeCreateView.as_view(), name='atividade_novo'),
    path('cadastros/atividades/<int:pk>/editar/', views.AtividadeUpdateView.as_view(), name='atividade_editar'),
    path('cadastros/atividades/<int:pk>/excluir/', views.AtividadeDeleteView.as_view(), name='atividade_excluir'),
    
    # CRUD Prioridade
    path('cadastros/prioridades/novo/', views.PrioridadeCreateView.as_view(), name='prioridade_novo'),
    path('cadastros/prioridades/<int:pk>/editar/', views.PrioridadeUpdateView.as_view(), name='prioridade_editar'),
    path('cadastros/prioridades/<int:pk>/excluir/', views.PrioridadeDeleteView.as_view(), name='prioridade_excluir'),
    
    # CRUD TipoProblema
    path('cadastros/tipoproblemas/novo/', views.TipoProblemaCreateView.as_view(), name='tipoproblema_novo'),
    path('cadastros/tipoproblemas/<int:pk>/editar/', views.TipoProblemaUpdateView.as_view(), name='tipoproblema_editar'),
    path('cadastros/tipoproblemas/<int:pk>/excluir/', views.TipoProblemaDeleteView.as_view(), name='tipoproblema_excluir'),
    
    # CRUD Projeto
    path('cadastros/projetos/novo/', views.ProjetoCreateView.as_view(), name='projeto_novo'),
    path('cadastros/projetos/<int:pk>/editar/', views.ProjetoUpdateView.as_view(), name='projeto_editar'),
    path('cadastros/projetos/<int:pk>/excluir/', views.ProjetoDeleteView.as_view(), name='projeto_excluir'),
    
    # CRUD Solicitante
    path('cadastros/solicitantes/novo/', views.SolicitanteCreateView.as_view(), name='solicitante_novo'),
    path('cadastros/solicitantes/<int:pk>/editar/', views.SolicitanteUpdateView.as_view(), name='solicitante_editar'),
    path('cadastros/solicitantes/<int:pk>/excluir/', views.SolicitanteDeleteView.as_view(), name='solicitante_excluir'),

    # Configurações
    path('configuracoes/', views.ConfiguracoesView.as_view(), name='configuracoes'),
    path('configuracoes/tema/', views.ConfiguracoesTemaView.as_view(), name='configuracoes_tema'),
    
    # API Endpoints
    path('api/responsaveis/', views.carregar_responsaveis, name='carregar_responsaveis'),
    path('cadastros/clientes/api/zonas/', views.api_zonas_por_corporacao, name='cliente_api_zonas'),
    path('cadastros/clientes/api/plantas/', views.api_plantas_por_corporacao_zona, name='cliente_api_plantas'),
    path('cadastros/clientes/api/zonas/', views.api_zonas_por_corporacao, name='cliente_api_zonas'),
    path('cadastros/clientes/api/plantas/', views.api_plantas_por_corporacao_zona, name='cliente_api_plantas'),
    path('cadastros/clientes/api/lista/', views.ClienteListaJsonView.as_view(), name='cliente_api_lista'),

    # Health Check
    path('health/', views.HealthCheckView.as_view(), name='health_check'),

    # Auth - Login por email
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(next_page='semeq:login'), name='logout'),
    path('senha/alterar/', auth_views.PasswordChangeView.as_view(
        template_name='registration/password_change.html',
        form_class=SemeqPasswordChangeForm,
        success_url=reverse_lazy('semeq:configuracoes')
    ), name='password_change'),
    
# Cadastro Público (domínios permitidos)
    path('cadastro/', views.PublicRegistrationView.as_view(), name='register'),
    
    # Password Reset
    path('senha/esqueci/', views.SemeqPasswordResetView.as_view(), name='password_reset'),
    path('senha/esqueci/enviado/', views.SemeqPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('senha/redefinir/<uidb64>/<token>/', views.SemeqPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('senha/redefinido/', views.SemeqPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]