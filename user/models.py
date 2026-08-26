from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from datetime import timedelta, time


class PerfilUsuario(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('gestor', 'Gestor'),
        ('lider', 'Líder'),
        ('usuario', 'Usuário'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='usuario')
    telefone = models.CharField(max_length=20, blank=True)
    ativo = models.BooleanField(default=True)
    time = models.ForeignKey('Time', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Time/Equipe")
    tema_preferido = models.CharField(
        max_length=10,
        choices=[('light', 'Claro'), ('dark', 'Escuro')],
        default='light',
        verbose_name="Tema Preferido"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    last_password_change = models.DateTimeField(null=True, blank=True, verbose_name="Última alteração de senha")

    def is_admin(self):
        return self.role == 'admin' or self.user.is_superuser

    def is_gestor_or_above(self):
        return self.role in ['admin', 'gestor'] or self.user.is_superuser

    def is_lider_or_above(self):
        return self.role in ['admin', 'gestor', 'lider'] or self.user.is_superuser

    def can_manage_users(self):
        return self.is_gestor_or_above()

    def can_manage_times(self):
        return self.is_admin()

    def can_manage_clientes(self):
        return self.is_gestor_or_above()

    def can_manage_equipamentos(self):
        return self.is_lider_or_above()

    def can_view_all_apontamentos(self):
        return self.is_gestor_or_above()

    def can_view_team_apontamentos(self):
        return self.is_lider_or_above()

    def get_visible_users(self):
        if self.is_gestor_or_above():
            return User.objects.filter(perfil__ativo=True).select_related('perfil')
        elif self.is_lider_or_above():
            return User.objects.filter(perfil__time=self.time, perfil__ativo=True).select_related('perfil')
        return User.objects.filter(id=self.user.id)

    def get_visible_times(self):
        if self.is_admin():
            return Time.objects.filter(ativo=True)
        elif self.is_gestor_or_above():
            return Time.objects.filter(ativo=True)
        elif self.is_lider_or_above():
            return Time.objects.filter(id=self.time_id)
        return Time.objects.none()

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"


class Time(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Time")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Time"
        verbose_name_plural = "Times"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Cliente(models.Model):
    corporation = models.CharField(max_length=200, verbose_name="Corporação")
    plant = models.CharField(max_length=200, verbose_name="Planta")
    # unat = models.CharField(max_length=200, blank=True, verbose_name="UNAT")
    # city = models.CharField(max_length=100, blank=True, verbose_name="Cidade")
    # state_province = models.CharField(max_length=50, blank=True, verbose_name="Estado/Província")
    # country = models.CharField(max_length=100, blank=True, verbose_name="País")
    # region = models.CharField(max_length=100, blank=True, verbose_name="Região")
    # business = models.CharField(max_length=200, blank=True, verbose_name="Negócio")
    zone = models.CharField(max_length=50, blank=True, verbose_name="Zona")
    # ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['corporation', 'plant']
        indexes = [
            models.Index(fields=['corporation']),
        ]

    def __str__(self):
        return f"{self.corporation} - {self.plant}"

    @property
    def nome_completo(self):
        return f"{self.corporation} / {self.plant}"


class Equipamento(models.Model):
    TIPO_CHOICES = [
        ('gateway', 'Gateway'),
        ('bomba', 'Bomba'),
        ('sensor', 'Sensor'),
        ('controlador', 'Controlador'),
        ('outro', 'Outro'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo")
    modelo = models.CharField(max_length=100, blank=True, verbose_name="Modelo")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"
        ordering = ['tipo', 'modelo']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.modelo or self.id}"


class Apontamento(models.Model):
    # Time thresholds for automatic classification (easily configurable)
    LIMITE_ATENDIMENTO_APOS_18H = time(18, 0)  # 18:00 - after this is "após 18h"
    LIMITE_ATENDIMENTO_ANTES_8H = time(8, 0)   # 08:00 - before this is "antes 8h"

    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]
    STATUS_CHOICES = [
        ('aberto', 'Aberto'),
        ('andamento', 'Em execução'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado'),
    ]
    ATIVIDADE_CHOICES = [
        ('suporte', 'Suporte'),
        ('instalacao', 'Instalação'),
        ('treinamento', 'Treinamento'),
        ('manutencao', 'Manutenção'),
    ]
    TIPO_PROBLEMA_CHOICES = [
        ('hardware', 'Hardware'),
        ('software', 'Software'),
        ('comunicacao', 'Comunicação'),
        ('configuracao', 'Configuração'),
    ]
    EQUIPE_CHOICES = [
        ('pmc', 'PMC'),
        ('shd', 'SHD'),
    ]
    DESVIO_CHOICES = [
        ('nenhum', 'Nenhum'),
        ('cliente', 'Cliente'),
        ('infraestrutura', 'Infraestrutura'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='apontamentos')
    projeto = models.CharField(max_length=200, verbose_name="Projeto")
    solicitante = models.CharField(max_length=200, verbose_name="Solicitante")
    ticket = models.CharField(max_length=100, verbose_name="Ticket")
    equipamento = models.ForeignKey(Equipamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='apontamentos')
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='media', verbose_name="Prioridade")
    
    equipe = models.CharField(max_length=10, choices=EQUIPE_CHOICES, verbose_name="Equipe")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='apontamentos_responsavel')
    atividade = models.CharField(max_length=20, choices=ATIVIDADE_CHOICES, verbose_name="Atividade")
    tipo_problema = models.CharField(max_length=20, choices=TIPO_PROBLEMA_CHOICES, verbose_name="Tipo do Problema")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aberto', verbose_name="Status")
    
    data = models.DateField(verbose_name="Data")
    hora_inicial = models.TimeField(verbose_name="Hora Inicial")
    hora_final = models.TimeField(verbose_name="Hora Final")
    tempo_total = models.DurationField(verbose_name="Tempo Total", null=True, blank=True)
    
    gw_ar = models.BooleanField(default=False, verbose_name="GW no Ar")
    desvio = models.CharField(max_length=20, choices=DESVIO_CHOICES, default='nenhum', verbose_name="Desvio")
    apos_18h = models.BooleanField(default=False, verbose_name="Trabalho após 18h")
    tempo_minutos = models.PositiveIntegerField(null=True, blank=True, verbose_name="Tempo (minutos)")
    
    descricao = models.TextField(verbose_name="Descrição do Apontamento")
    
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='apontamentos_criados')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Apontamento"
        verbose_name_plural = "Apontamentos"
        ordering = ['-data', '-hora_inicial']
        indexes = [
            models.Index(fields=['data']),
            models.Index(fields=['status']),
            models.Index(fields=['responsavel']),
            models.Index(fields=['cliente']),
        ]

    def __str__(self):
        return f"#{self.ticket} - {self.cliente} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Calcula tempo total
        if self.tempo_minutos:
            # Se tempo_minutos foi preenchido, usa ele
            from datetime import timedelta
            self.tempo_total = timedelta(minutes=self.tempo_minutos)
        elif self.hora_inicial and self.hora_final:
            # Senão, calcula a partir das horas
            from datetime import datetime
            inicio = datetime.combine(self.data, self.hora_inicial)
            fim = datetime.combine(self.data, self.hora_final)
            if fim < inicio:
                fim += timedelta(days=1)
            self.tempo_total = fim - inicio
        
        super().save(*args, **kwargs)