from __future__ import annotations

from datetime import date, datetime, time, timedelta
from django.db import transaction
from django.core.exceptions import ValidationError

from user.models import Apontamento, ApontamentoTempo, Status


def gerar_numero_sequencial(data_apontamento: date) -> int:
    date_prefix = data_apontamento.strftime('%Y%m%d')
    base = int(f"{date_prefix}000")
    limit = int(f"{date_prefix}999")

    last = Apontamento.objects.filter(
        numero_sequencial__gte=base,
        numero_sequencial__lt=limit
    ).order_by('-numero_sequencial').first()

    if last:
        return last.numero_sequencial + 1
    return int(f"{date_prefix}001")


def calcular_tempo_total(data: date, hora_inicial: time, hora_final: time) -> timedelta | None:
    if not (hora_inicial and hora_final):
        return None

    # Se as horas são iguais, retorna 0 (não adiciona 24h)
    if hora_inicial == hora_final:
        return timedelta(0)

    dt_inicial = datetime.combine(data, hora_inicial)
    dt_final = datetime.combine(data, hora_final)

    if dt_final <= dt_inicial:
        dt_final += timedelta(days=1)

    return dt_final - dt_inicial


def calcular_tempo_atendimento(data: date, inicio: time | None, fim: time | None) -> int | None:
    if not (inicio and fim):
        return None

    dt_ini = datetime.combine(data, inicio)
    dt_fim = datetime.combine(data, fim)

    if dt_fim <= dt_ini:
        dt_fim += timedelta(days=1)

    delta = dt_fim - dt_ini
    return int(delta.total_seconds() / 60)


# =====================================================================
# NOVOS MODELOS: ATENDIMENTO & APONTAMENTO TEMPO
# =====================================================================

@transaction.atomic
def criar_atendimento(
    *,
    responsavel,
    criado_por,
    cliente,
    data_inicial: date,
    data_final: date,
    descricao: str,
    **campos_extras
) -> Atendimento:
    numero_seq = gerar_numero_sequencial(data_inicial)

    at = Atendimento.objects.create(
        numero_sequencial=numero_seq,
        responsavel=responsavel,
        criado_por=criado_por,
        cliente=cliente,
        data_inicial=data_inicial,
        data_final=data_final,
        descricao=descricao,
        **campos_extras
    )
    return at


@transaction.atomic
def criar_apontamento_tempo(
    *,
    atendimento: Atendimento,
    responsavel,
    criado_por,
    data: date,
    hora_inicial: time,
    hora_final: time,
    observacao: str = "",
    tempo_investido_minutos: int | None = None,
) -> ApontamentoTempo:
    # Check for existing apontamento for same atendimento and data
    if ApontamentoTempo.objects.filter(atendimento=atendimento, data=data).exists():
        raise ValidationError(
            f'Já existe um apontamento para este atendimento na data {data.strftime("%d/%m/%Y")}.'
        )
    
    tempo_total = calcular_tempo_total(data, hora_inicial, hora_final)
    tempo_total_minutos = int(tempo_total.total_seconds() / 60) if tempo_total else 0

    ap = ApontamentoTempo.objects.create(
        atendimento=atendimento,
        responsavel=responsavel,
        criado_por=criado_por,
        data=data,
        hora_inicial=hora_inicial,
        hora_final=hora_final,
        tempo_total=tempo_total,
        tempo_total_minutos=tempo_total_minutos,
        tempo_investido_minutos=tempo_investido_minutos,
        observacao=observacao,
    )
    return ap


@transaction.atomic
def atualizar_apontamento_tempo(apontamento: ApontamentoTempo, **dados) -> ApontamentoTempo:
    hora_inicial = dados.get('hora_inicial', apontamento.hora_inicial)
    hora_final = dados.get('hora_final', apontamento.hora_final)
    data = dados.get('data', apontamento.data)
    tempo_investido_minutos = dados.get('tempo_investido_minutos', apontamento.tempo_investido_minutos)
    
    # Validate unique constraint if data is being changed
    if 'data' in dados and data != apontamento.data:
        if ApontamentoTempo.objects.filter(atendimento=apontamento.atendimento, data=data).exists():
            raise ValidationError(
                f'Já existe um apontamento para este atendimento na data {data.strftime("%d/%m/%Y")}.'
            )
    
    if 'hora_inicial' in dados or 'hora_final' in dados or 'data' in dados:
        tempo_total = calcular_tempo_total(data, hora_inicial, hora_final)
        dados['tempo_total'] = tempo_total
        if tempo_total:
            dados['tempo_total_minutos'] = int(tempo_total.total_seconds() / 60)
    
    # Handle tempo_investido_minutos
    if 'tempo_investido_minutos' in dados:
        dados['tempo_investido_minutos'] = tempo_investido_minutos
    
    for campo, valor in dados.items():
        setattr(apontamento, campo, valor)
    
    apontamento.save(update_fields=list(dados.keys()))
    return apontamento


def pode_editar(apontamento: Apontamento) -> bool:
    # Allow editing regardless of status
    return True


def get_status_concluido() -> Status | None:
    return Status.objects.filter(status='concluido', ativo=True).first()


# =====================================================================
# MODELOS LEGADOS (APONTAMENTO) - PARA COMPATIBILIDADE
# =====================================================================

@transaction.atomic
def criar_apontamento(
    *,
    responsavel,
    criado_por,
    cliente,
    data: date,
    hora_inicial: time,
    hora_final: time,
    descricao: str,
    **campos_extras
) -> Apontamento:
    Apontamento.objects.select_for_update().filter(
        responsavel=responsavel,
        data=data
    ).exists()

    numero_seq = gerar_numero_sequencial(data)
    tempo_total = calcular_tempo_total(data, hora_inicial, hora_final)
    tempo_atendimento_min = calcular_tempo_atendimento(
        data,
        hora_inicial,
        hora_final
    )

    ap = Apontamento.objects.create(
        numero_sequencial=numero_seq,
        responsavel=responsavel,
        criado_por=criado_por,
        cliente=cliente,
        data=data,
        data_inicial=data,
        data_final=data,
        tempo_investido_minutos=tempo_atendimento_min,
        descricao=descricao,
        **campos_extras
    )
    return ap


@transaction.atomic
def atualizar_apontamento(apontamento: Apontamento, **dados) -> Apontamento:
    # Handle date fields from form (data_inicial, data_final)
    data_inicial = dados.get('data_inicial')
    data_final = dados.get('data_final')
    tempo_investido_minutos = dados.get('tempo_investido_minutos')

    if data_inicial is not None:
        dados['data_inicial'] = data_inicial
        # Auto-populate 'data' from 'data_inicial' for backward compatibility
        if not dados.get('data'):
            dados['data'] = data_inicial

    if data_final is not None:
        dados['data_final'] = data_final

    # Keep explicit tempo_investido_minutos if provided (form field)
    if tempo_investido_minutos is not None:
        dados['tempo_investido_minutos'] = tempo_investido_minutos

    for campo, valor in dados.items():
        setattr(apontamento, campo, valor)

    apontamento.save(update_fields=list(dados.keys()))

    # Sync with ApontamentoTempo for list view consistency
    # Use data_inicial (or existing data) as the date for ApontamentoTempo
    sync_data = data_inicial or apontamento.data_inicial or apontamento.data
    if sync_data and tempo_investido_minutos is not None:
        # Get or create ApontamentoTempo for this date
        at, created = ApontamentoTempo.objects.get_or_create(
            apontamento=apontamento,
            data=sync_data,
            defaults={
                'responsavel': apontamento.responsavel,
                'criado_por': apontamento.criado_por,
                'hora_inicial': time(8, 0),
                'hora_final': time(8, 0),
                'tempo_investido_minutos': tempo_investido_minutos,
                'observacao': 'Atualizado via edição do apontamento principal'
            }
        )
        if not created:
            at.tempo_investido_minutos = tempo_investido_minutos
            at.save(update_fields=['tempo_investido_minutos'])

    return apontamento