"""
Management command to seed test apontamentos for all active users.
Deletes all existing apontamentos and creates test data for each user.
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from user.models import Cliente, Projeto, Solicitante, Status, Prioridade, Atividade, TipoProblema, Equipe, Apontamento

User = get_user_model()

class Command(BaseCommand):
    help = 'Limpa todos os apontamentos e cria dados de teste para cada usuário ativo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apontamentos-por-usuario',
            type=int,
            default=2,
            help='Número de apontamentos a criar por usuário (default: 2)'
        )
        parser.add_argument(
            '--no-delete',
            action='store_true',
            help='Não apagar apontamentos existentes, apenas adicionar novos'
        )

    def handle(self, *args, **options):
        apontamentos_por_usuario = options['apontamentos_por_usuario']
        no_delete = options['no_delete']

        # 1. Apaga todos os apontamentos existentes
        if not no_delete:
            count = Apontamento.objects.count()
            Apontamento.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Apagados {count} apontamentos existentes'))

        # Busca dados necessários
        clientes = list(Cliente.objects.filter(ativo=True))
        projetos = list(Projeto.objects.filter(ativo=True))
        solicitantes = list(Solicitante.objects.filter(ativo=True))
        usuarios = User.objects.filter(is_active=True).select_related('perfil')
        status_objs = list(Status.objects.filter(ativo=True))
        prioridades = list(Prioridade.objects.filter(ativo=True))
        atividades = list(Atividade.objects.filter(ativo=True))
        tipos_problema = list(TipoProblema.objects.filter(ativo=True))
        equipes = list(Equipe.objects.filter(ativo=True))

        if not status_objs:
            self.stdout.write(self.style.ERROR('Nenhum status ativo encontrado. Execute setup_admin primeiro.'))
            return

        if not usuarios.exists():
            self.stdout.write(self.style.ERROR('Nenhum usuário ativo encontrado.'))
            return

        self.stdout.write(f'Encontrados {usuarios.count()} usuários ativos')
        self.stdout.write(f'Status disponíveis: {len(status_objs)}')
        self.stdout.write(f'Clientes: {len(clientes)}, Projetos: {len(projetos)}, Solicitantes: {len(solicitantes)}')

        # Cria apontamentos para cada usuário
        total_criados = 0
        for user in usuarios:
            user_equipe = getattr(user.perfil, 'equipe', None) if hasattr(user, 'perfil') else None
            
            for i in range(apontamentos_por_usuario):
                # Varia o status
                status = random.choice(status_objs)
                
                # Varia a data (hoje e dias anteriores)
                dias_atras = i * 2  # 0, 2, 4, 6...
                data_inicial = date.today() - timedelta(days=dias_atras)
                
                # Seleciona cliente, projeto, solicitante aleatórios (se existirem)
                cliente = random.choice(clientes) if clientes else None
                projeto = random.choice(projetos) if projetos else None
                solicitante = random.choice(solicitantes) if solicitantes else None
                atividade = random.choice(atividades) if atividades else None
                tipo_problema = random.choice(tipos_problema) if tipos_problema else None
                prioridade = random.choice(prioridades) if prioridades else None
                equipe = user_equipe or (random.choice(equipes) if equipes else None)
                
                # Tempo investido
                tempo_minutos = random.randint(10, 120)
                
                # Se status for Concluído, garante tempo > 0
                if status.is_concluido and tempo_minutos == 0:
                    tempo_minutos = random.randint(30, 240)

                try:
                    Apontamento.objects.create(
                        responsavel=user,
                        equipe=equipe,
                        cliente=cliente,
                        projeto=projeto,
                        solicitante=solicitante,
                        atividade=atividade,
                        tipo_problema=tipo_problema,
                        prioridade=prioridade,
                        status=status,
                        data_inicial=data_inicial,
                        tempo_investido_minutos=tempo_minutos,
                        descricao=f'Apontamento de teste #{i+1} para {user.get_full_name() or user.username}',
                        criado_por=user,
                    )
                    total_criados += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Erro ao criar apontamento para {user.username}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n[OK] Seed concluido! {total_criados} apontamentos criados para {usuarios.count()} usuarios.'
        ))