from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import PerfilUsuario, Cliente, Equipamento, Time, Equipe, Apontamento


class ClienteResource(resources.ModelResource):
    class Meta:
        model = Cliente
        fields = (
            'id', 'corporation','plant', 'zone'
        )
        export_order = fields
        # import_id_fields = ('corporation_id', 'plant_id')


@admin.register(Cliente)
class ClienteAdmin(ImportExportModelAdmin):
    resource_class = ClienteResource
    list_display = ('corporation', 'plant', 'criado_em')
    search_fields = ('corporation','plant')
    ordering = ('corporation', 'plant')
    list_per_page = 25


class EquipamentoInline(admin.TabularInline):
    model = Equipamento
    extra = 1
    fields = ('tipo', 'device', 'modelo',)
    readonly_fields = ('criado_em',)


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'device', 'modelo', 'ativo', 'criado_em',)
    list_filter = ('tipo', 'ativo',)
    search_fields = ('device', 'modelo',)
    ordering = ('tipo', 'device', 'modelo',)
    list_per_page = 25


@admin.register(Time)
class TimeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo', 'criado_em')
    list_filter = ('ativo',)
    search_fields = ('nome',)
    list_editable = ('ativo',)
    ordering = ('nome',)


@admin.register(Equipe)
class EquipeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo', 'ordem', 'criado_em')
    list_filter = ('ativo',)
    search_fields = ('nome',)
    list_editable = ('ativo', 'ordem')
    ordering = ('ordem', 'nome')


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'equipe', 'ativo', 'telefone', 'criado_em')
    list_filter = ('role', 'ativo', 'equipe')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')
    list_editable = ('role', 'ativo', 'equipe')
    raw_id_fields = ('user',)


@admin.register(Apontamento)
class ApontamentoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'responsavel', 'equipe', 'status', 'data_inicial', 'criado_em')
    list_filter = ('status', 'equipe', 'atividade', 'tipo_problema', 'prioridade', 'data_inicial', 'cliente')
    search_fields = ('projeto', 'solicitante', 'responsavel__username', 'cliente__corporation')
    date_hierarchy = 'data_inicial'
    ordering = ('-data_inicial', '-data_final')
    list_per_page = 25
    raw_id_fields = ('cliente', 'equipamento', 'responsavel', 'criado_por')