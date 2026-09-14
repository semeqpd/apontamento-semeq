from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum
from datetime import time


class Time(models.Model):
    """Modelo para gerenciar Times/Equipes."""
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


class PerfilUsuario(models.Model):
    """Perfil estendido do usuário com role, equipe, telefone, etc."""
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('gestor', 'Gestor'),
        ('lider', 'Líder'),
        ('colaborador', 'Colaborador'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name="Usuário"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='colaborador',
        verbose_name="Função"
    )
    telefone = models.CharField(max_length=20, blank=True, verbose_name="Telefone")
    equipe = models.ForeignKey(
        'Equipe',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Equipe"
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    email_verificado = models.BooleanField(default=False, verbose_name="Email verificado")
    email_verificado_em = models.DateTimeField(blank=True, null=True, verbose_name="Email verificado em")
    tema_preferido = models.CharField(max_length=20, default='light', verbose_name="Tema preferido")
    last_password_change = models.DateTimeField(blank=True, null=True, verbose_name="Última troca de senha")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    def is_admin(self) -> bool:
        return self.role == 'admin' or self.user.is_superuser

    def is_gestor(self) -> bool:
        return self.role in ('admin', 'gestor') or self.user.is_superuser

    def is_lider(self) -> bool:
        return self.role in ('admin', 'gestor', 'lider') or self.user.is_superuser

    def is_colaborador(self) -> bool:
        return self.role == 'colaborador'

    # Aliases for backward compatibility
    is_gestor_or_above = is_gestor
    is_lider_or_above = is_lider

    def get_visible_users(self):
        User = get_user_model()
        if self.is_gestor():
            return User.objects.filter(perfil__ativo=True).select_related('perfil')
        if self.is_lider():
            return User.objects.filter(
                perfil__ativo=True, perfil__equipe=self.equipe
            ).select_related('perfil')
        return User.objects.filter(id=self.user.id)

    def can_manage_clientes(self) -> bool:
        return self.is_gestor()

    def can_manage_users(self) -> bool:
        return self.is_gestor()

    def can_manage_equipamentos(self) -> bool:
        return self.is_gestor()


class Cliente(models.Model):
    """Modelo para gerenciar Clientes (Corporação + Planta + Zona)."""
    corporation = models.CharField(max_length=200, verbose_name="Corporação", db_index=True)
    plant = models.CharField(max_length=200, verbose_name="Planta", db_index=True)
    plant_id = models.CharField(max_length=50, blank=True, verbose_name="ID da Planta", db_index=True)
    zone = models.CharField(max_length=50, blank=True, verbose_name="Zona")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['corporation', 'plant']
        unique_together = [['corporation', 'plant', 'zone']]
        indexes = [
            models.Index(fields=['corporation', 'plant'], name='cliente_corp_plant_idx'),
        ]

    def __str__(self):
        return f"{self.corporation} - {self.plant}" + (f" - {self.zone}" if self.zone else "")


class Equipamento(models.Model):
    """Modelo para gerenciar Equipamentos."""

    nome = models.CharField(max_length=100, verbose_name="Nome", default="Equipamento")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de Exibição")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['ativo', 'ordem'], name='equipamento_ativo_ordem_idx'),
        ]

    def __str__(self):
        return self.nome


class Status(models.Model):
    """Modelo para gerenciar Status de apontamentos dinamicamente."""
    status = models.CharField(max_length=200, unique=True, verbose_name="Status")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de Exibição")
    cor = models.CharField(max_length=7, default='#6c757d', verbose_name="Cor (Hex)")
    is_concluido = models.BooleanField(default=False, verbose_name="Status de Conclusão")
    criado_em = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Status"
        verbose_name_plural = "Status"
        ordering = ['ordem', 'status']
        indexes = [
            models.Index(fields=['ativo', 'ordem'], name='status_ativo_ordem_idx'),
            models.Index(fields=['status'], name='status_nome_idx'),
        ]

    def __str__(self):
        return self.status

    @property
    def is_fixo(self):
        """Retorna True se for um dos 3 status fixos do sistema."""
        return self.status.lower() in ['aberto', 'executando', 'concluído', 'concluido']

    @property
    def is_concluido_fixo(self):
        """Retorna True se for o status fixo de Conclusão."""
        return self.is_concluido and self.status.lower() in ['concluído', 'concluido']

    def can_edit_name(self):
        """Verifica se o nome pode ser editado (não é status fixo)."""
        return not self.is_fixo

    def can_delete(self):
        """Verifica se pode ser deletado (não é status fixo)."""
        return not self.is_fixo

    @classmethod
    def get_next_ordem(cls):
        """Retorna a próxima ordem disponível (max + 1)."""
        max_ordem = cls.objects.aggregate(max_ordem=models.Max('ordem'))['max_ordem']
        return (max_ordem or 0) + 1


class Atividade(models.Model):
    """Modelo para gerenciar Atividades dinamicamente."""
    nome = models.CharField(max_length=200, unique=True, verbose_name="Atividade")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de Exibição")
    criado_em = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Atividade"
        verbose_name_plural = "Atividades"
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['ativo', 'ordem'], name='atividade_ativo_ordem_idx'),
            models.Index(fields=['nome'], name='atividade_nome_idx'),
        ]

    def __str__(self):
        return self.nome

    @classmethod
    def get_next_ordem(cls):
        """Retorna a próxima ordem disponível (max + 1)."""
        max_ordem = cls.objects.aggregate(max_ordem=models.Max('ordem'))['max_ordem']
        return (max_ordem or 0) + 1


class Prioridade(models.Model):
    """Modelo para gerenciar Prioridades dinamicamente."""
    nome = models.CharField(max_length=200, unique=True, verbose_name="Prioridade")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de Exibição")
    cor = models.CharField(max_length=7, default='#6c757d', verbose_name="Cor (Hex)")
    criado_em = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Prioridade"
        verbose_name_plural = "Prioridades"
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['ativo', 'ordem'], name='prioridade_ativo_ordem_idx'),
            models.Index(fields=['nome'], name='prioridade_nome_idx'),
        ]

    def __str__(self):
        return self.nome

    @classmethod
    def get_next_ordem(cls):
        """Retorna a próxima ordem disponível (max + 1)."""
        max_ordem = cls.objects.aggregate(max_ordem=models.Max('ordem'))['max_ordem']
        return (max_ordem or 0) + 1


class TipoProblema(models.Model):
    """Modelo para gerenciar Tipos de Problema dinamicamente."""
    nome = models.CharField(max_length=200, unique=True, verbose_name="Tipo de Problema")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de Exibição")
    criado_em = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Tipo de Problema"
        verbose_name_plural = "Tipos de Problema"
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['ativo', 'ordem'], name='tipoproblema_ativo_ordem_idx'),
            models.Index(fields=['nome'], name='tipoproblema_nome_idx'),
        ]

    def __str__(self):
        return self.nome

    @classmethod
    def get_next_ordem(cls):
        """Retorna a próxima ordem disponível (max + 1)."""
        max_ordem = cls.objects.aggregate(max_ordem=models.Max('ordem'))['max_ordem']
        return (max_ordem or 0) + 1

    # Time thresholds for automatic classification (easily configurable)
    LIMITE_ATENDIMENTO_APOS_18H = time(18, 0)  # 18:00 - after this is "após 18h"
    LIMITE_ATENDIMENTO_ANTES_8H = time(8, 0)   # 08:00 - before this is "antes 8h"

    DESVIO_CHOICES = [
        ('nenhum', 'Nenhum'),
        ('cliente', 'Cliente'),
        ('infraestrutura', 'Infraestrutura'),
    ]


class Equipe(models.Model):
    """Modelo para gerenciar Equipes (PMC, SHD, etc.) dinamicamente."""
    nome = models.CharField(max_length=200, unique=True, verbose_name="Equipe")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de Exibição")
    criado_em = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Equipe"
        verbose_name_plural = "Equipes"
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['ativo', 'ordem'], name='equipe_ativo_ordem_idx'),
            models.Index(fields=['nome'], name='equipe_nome_idx'),
        ]

    def __str__(self):
        return self.nome

    @classmethod
    def get_next_ordem(cls):
        """Retorna a próxima ordem disponível (max + 1)."""
        max_ordem = cls.objects.aggregate(max_ordem=models.Max('ordem'))['max_ordem']
        return (max_ordem or 0) + 1


class Projeto(models.Model):
    """Modelo para gerenciar Projetos dinamicamente."""
    nome = models.CharField(max_length=200, unique=True, verbose_name="Projeto")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de Exibição")
    criado_em = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['ativo', 'ordem'], name='projeto_ativo_ordem_idx'),
            models.Index(fields=['nome'], name='projeto_nome_idx'),
        ]

    def __str__(self):
        return self.nome

    @classmethod
    def get_next_ordem(cls):
        """Retorna a próxima ordem disponível (max + 1)."""
        max_ordem = cls.objects.aggregate(max_ordem=models.Max('ordem'))['max_ordem']
        return (max_ordem or 0) + 1


class Solicitante(models.Model):
    """Modelo para gerenciar Solicitantes dinamicamente."""
    nome = models.CharField(max_length=200, unique=True, verbose_name="Solicitante")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de Exibição")
    criado_em = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Solicitante"
        verbose_name_plural = "Solicitantes"
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['ativo', 'ordem'], name='solicitante_ativo_ordem_idx'),
            models.Index(fields=['nome'], name='solicitante_nome_idx'),
        ]

    def __str__(self):
        return self.nome

    @classmethod
    def get_next_ordem(cls):
        """Retorna a próxima ordem disponível (max + 1)."""
        max_ordem = cls.objects.aggregate(max_ordem=models.Max('ordem'))['max_ordem']
        return (max_ordem or 0) + 1





class Apontamento(models.Model):
    """Modelo para apontamentos/tarefas - representa o trabalho/solicitação em si.
    Contém dados que não mudam a cada registro de horas.
    """
    
    class Meta:
        db_table = 'user_apontamento'
        verbose_name = "Apontamento"
        verbose_name_plural = "Apontamentos"
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['data_inicial']),
            models.Index(fields=['status']),
            models.Index(fields=['responsavel']),
            models.Index(fields=['cliente']),
        ]

    # ID automático sequencial (formato: YYYYMMDDNNN)
    numero_sequencial = models.PositiveBigIntegerField(
        unique=True,
        blank=True,
        null=True,
        verbose_name="Número Sequencial"
    )
    
    # Ticket
    ticket = models.CharField(max_length=100, unique=True, blank=True, null=True, verbose_name="Ticket")
    
    # Dados do Apontamento (estáticos)
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Projeto"
    )
    solicitante = models.ForeignKey(
        Solicitante,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Solicitante"
    )
    
    # FKs to dynamic models
    prioridade = models.ForeignKey(
        Prioridade,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Prioridade"
    )
    equipe = models.ForeignKey(
        Equipe,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Equipe"
    )
    atividade = models.ForeignKey(
        Atividade,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Atividade"
    )
    tipo_problema = models.ForeignKey(
        TipoProblema,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Tipo do Problema"
    )
    status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Status"
    )
    
    # Período do apontamento
    data = models.DateField(verbose_name="Data")
    data_inicial = models.DateField(blank=True, null=True, verbose_name="Data Inicial")
    data_final = models.DateField(blank=True, null=True, verbose_name="Data Final")
    
    descricao = models.TextField(verbose_name="Descrição do Apontamento")
    
    # Tempo investido no apontamento (manual - opcional, usado para somar ao total)
    tempo_investido_minutos = models.PositiveIntegerField(
        blank=True, null=True, default=0,
        verbose_name="Tempo Investido (minutos)",
    )
    
    # FKs
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='apontamentos',
        verbose_name="Cliente"
    )
    equipamento = models.ForeignKey(
        Equipamento,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='apontamentos',
        verbose_name="Equipamento"
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='apontamentos_responsavel',
        verbose_name="Responsável"
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='apontamentos_criados',
        verbose_name="Criado por"
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.numero_sequencial} - {self.cliente} - {self.responsavel.get_full_name() or self.responsavel.username}"
    
    def tempo_minutos(self) -> int | None:
        return self.tempo_investido_minutos
    
    @property
    def tempo_investido_formatado(self) -> str:
        """Retorna tempo investido formatado para exibição (ex: '9h 30min' ou '540min')."""
        total_min = self.tempo_investido_minutos or 0
        if total_min == 0:
            return "0min"
        horas = total_min // 60
        minutos = total_min % 60
        if horas > 0 and minutos > 0:
            return f"{horas}h {minutos}min"
        elif horas > 0:
            return f"{horas}h"
        else:
            return f"{minutos}min"
    
    @property
    def tempo_total_minutos(self) -> int:
        """Soma total de minutos de todos os apontamentos de tempo deste apontamento."""
        total = 0
        for ap in self.apontamentos_tempo.all():
            total += ap.get_tempo_exibicao_minutos
        return total
    
    @property
    def tempo_total_formatado(self) -> str:
        """Retorna tempo total formatado para exibição (ex: '9h 30min' ou '540min')."""
        total_min = self.tempo_total_minutos
        if total_min == 0:
            return "0min"
        horas = total_min // 60
        minutos = total_min % 60
        if horas > 0 and minutos > 0:
            return f"{horas}h {minutos}min"
        elif horas > 0:
            return f"{horas}h"
        else:
            return f"{minutos}min"
    
    def save(self, *args, **kwargs):
        # Auto-populate 'data' from 'data_inicial' if not set
        if not self.data and self.data_inicial:
            self.data = self.data_inicial
        if not self.numero_sequencial and self.data_inicial:
            from apps.apontamentos.services.apontamento_service import gerar_numero_sequencial
            self.numero_sequencial = gerar_numero_sequencial(self.data_inicial)
        # Auto-generate ticket if not provided
        if not self.ticket and self.numero_sequencial:
            self.ticket = f"TK-{self.numero_sequencial}"
        super().save(*args, **kwargs)


class ApontamentoTempo(models.Model):
    """Modelo para apontamentos de tempo - registros de horas trabalhadas.
    Um apontamento pode ter vários apontamentos de tempo.
    """
    
    apontamento = models.ForeignKey(
        Apontamento,
        on_delete=models.CASCADE,
        related_name='apontamentos_tempo',
        verbose_name="Apontamento"
    )
    
    data = models.DateField(verbose_name="Data")
    hora_inicial = models.TimeField(verbose_name="Hora Inicial")
    hora_final = models.TimeField(verbose_name="Hora Final")
    tempo_total = models.DurationField(blank=True, null=True, verbose_name="Tempo Total (calculado)")
    tempo_total_minutos = models.PositiveIntegerField(blank=True, null=True, verbose_name="Tempo Total Calculado (minutos)")
    
    # Campo manual para tempo realmente investido (opcional - sobrescreve o calculado)
    tempo_investido_minutos = models.PositiveIntegerField(
        blank=True, null=True, 
        verbose_name="Tempo Investido (minutos)",
        help_text="Tempo realmente trabalhado (opcional - se preenchido, sobrescreve o tempo calculado de hora_inicial até hora_final)"
    )
    
    observacao = models.TextField(blank=True, verbose_name="Observação")
    
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='apontamentos_tempo',
        verbose_name="Responsável"
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='apontamentos_tempo_criados',
        verbose_name="Criado por"
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Apontamento de Tempo"
        verbose_name_plural = "Apontamentos de Tempo"
        ordering = ['-data', '-hora_inicial']
        indexes = [
            models.Index(fields=['apontamento', 'data']),
            models.Index(fields=['responsavel', 'data']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['apontamento', 'data'],
                name='uniq_apontamentotempo_apontamento_data'
            ),
            models.CheckConstraint(
                condition=models.Q(hora_final__gt=models.F('hora_inicial')),
                name='apontamentotempo_hora_final_gt_inicial'
            ),
]
    
    def __str__(self):
        return f"{self.apontamento} - {self.data} ({self.get_tempo_exibicao})"
    
    @property
    def tempo_calculado_minutos(self) -> int:
        """Tempo calculado automaticamente de hora_inicial até hora_final."""
        if self.hora_inicial and self.hora_final and self.data:
            from apps.apontamentos.services.apontamento_service import calcular_tempo_total
            from datetime import datetime
            data_obj = self.data if isinstance(self.data, str) else self.data
            if isinstance(data_obj, str):
                data_obj = datetime.strptime(data_obj, '%Y-%m-%d').date()
            hora_i = self.hora_inicial if isinstance(self.hora_inicial, time) else datetime.strptime(self.hora_inicial, '%H:%M').time()
            hora_f = self.hora_final if isinstance(self.hora_final, time) else datetime.strptime(self.hora_final, '%H:%M').time()
            tempo = calcular_tempo_total(data_obj, hora_i, hora_f)
            return int(tempo.total_seconds() / 60) if tempo else 0
        return 0
    
    @property
    def get_tempo_exibicao_minutos(self) -> int:
        """Retorna o tempo a ser exibido: manual se preenchido, senão calculado."""
        if self.tempo_investido_minutos:
            return self.tempo_investido_minutos
        return self.tempo_calculado_minutos
    
    @property
    def get_tempo_exibicao(self) -> str:
        """Retorna tempo formatado para exibição."""
        total_min = self.get_tempo_exibicao_minutos
        if total_min == 0:
            return "0min"
        horas = total_min // 60
        minutos = total_min % 60
        if horas > 0 and minutos > 0:
            return f"{horas}h {minutos}min"
        elif horas > 0:
            return f"{horas}h"
        else:
            return f"{minutos}min"
    
    @property
    def usa_tempo_manual(self) -> bool:
        """Indica se está usando tempo manual em vez do calculado."""
        return bool(self.tempo_investido_minutos)
    
    def save(self, *args, **kwargs):
        # Calcular tempo_total e tempo_total_minutos automaticamente
        if self.hora_inicial and self.hora_final and self.data:
            from apps.apontamentos.services.apontamento_service import calcular_tempo_total
            from datetime import datetime
            if isinstance(self.data, str):
                self.data = datetime.strptime(self.data, '%Y-%m-%d').date()
            if isinstance(self.hora_inicial, str):
                self.hora_inicial = datetime.strptime(self.hora_inicial, '%H:%M').time()
            if isinstance(self.hora_final, str):
                self.hora_final = datetime.strptime(self.hora_final, '%H:%M').time()
            self.tempo_total = calcular_tempo_total(self.data, self.hora_inicial, self.hora_final)
            if self.tempo_total:
                self.tempo_total_minutos = int(self.tempo_total.total_seconds() / 60)
        super().save(*args, **kwargs)


class EmailVerificationToken(models.Model):
    """Token para verificação de email."""
    import uuid
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_verification_token'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    usado = models.BooleanField(default=False)
    usado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Token de Verificação de Email"
        verbose_name_plural = "Tokens de Verificação de Email"
        indexes = [
            models.Index(fields=['expira_em'], name='emailtoken_expira_idx'),
            models.Index(fields=['usado', 'expira_em'], name='emailtoken_usado_expira_idx'),
        ]

    def __str__(self):
        return f"Token para {self.user.email}"

    def is_valid(self):
        return not self.usado and self.expira_em > timezone.now()

    def mark_used(self):
        self.usado = True
        self.usado_em = timezone.now()
        self.save(update_fields=['usado', 'usado_em'])