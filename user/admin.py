from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import PerfilUsuario, Cliente, Equipamento, Time, Apontamento


class ClienteResource(resources.ModelResource):
    class Meta:
        model = Cliente
        fields = (
            'id', 'corporation_id', 'corporation', 'plant_id', 'plant',
            'unat', 'city', 'state_province', 'country', 'iso_3166',
            'region', 'business', 'sap_bp_code', 'zone', 'ativo'
        )
        export_order = fields
        import_id_fields = ('corporation_id', 'plant_id')


@admin.register(Cliente)
class ClienteAdmin(ImportExportModelAdmin):
    resource_class = ClienteResource
    list_display = ('corporation', 'plant', 'city', 'state_province', 'country', 'ativo', 'criado_em')
    list_filter = ('ativo', 'country', 'state_province', 'region', 'business')
    search_fields = ('corporation_id', 'corporation', 'plant_id', 'plant', 'city', 'sap_bp_code')
    list_editable = ('ativo',)
    ordering = ('corporation', 'plant')
    list_per_page = 25


class EquipamentoInline(admin.TabularInline):
    model = Equipamento
    extra = 1
    fields = ('tipo', 'numero_serie', 'modelo', 'ativo')
    readonly_fields = ('criado_em',)


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'numero_serie', 'modelo', 'cliente', 'ativo', 'criado_em')
    list_filter = ('tipo', 'ativo', 'cliente__corporation')
    search_fields = ('numero_serie', 'modelo', 'cliente__corporation', 'cliente__plant')
    list_editable = ('ativo',)
    ordering = ('cliente', 'tipo', 'numero_serie')
    list_per_page = 25


@admin.register(Time)
class TimeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo', 'criado_em')
    list_filter = ('ativo',)
    search_fields = ('nome',)
    list_editable = ('ativo',)
    ordering = ('nome',)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'time', 'ativo', 'telefone', 'criado_em')
    list_filter = ('role', 'ativo', 'time')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')
    list_editable = ('role', 'ativo', 'time')
    raw_id_fields = ('user',)


@admin.register(Apontamento)
class ApontamentoAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'cliente', 'responsavel', 'equipe', 'status', 'data', 'criado_em')
    list_filter = ('status', 'equipe', 'atividade', 'tipo_problema', 'prioridade', 'data', 'cliente')
    search_fields = ('ticket', 'projeto', 'solicitante', 'responsavel__username', 'cliente__corporation')
    date_hierarchy = 'data'
    ordering = ('-data', '-hora_inicial')
    list_per_page = 25
    raw_id_fields = ('cliente', 'equipamento', 'responsavel', 'criado_por')