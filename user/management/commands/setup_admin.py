from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.management import call_command
from user.models import (
    PerfilUsuario, Equipe, Cliente, TipoProblema, 
    Atividade, Prioridade, Status, Equipamento,
    Projeto, Solicitante
)
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Configura o administrador e cadastros padrão do sistema. Idempotente - pode ser executado múltiplas vezes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--migrate',
            action='store_true',
            help='Executa migrações antes do setup.',
        )

    def handle(self, *args, **options):
        if options.get('migrate'):
            self.stdout.write('[0/7] Executando migrações...')
            call_command('migrate', '--noinput')
            self.stdout.write(self.style.SUCCESS('  OK - Migrações aplicadas'))

        self.stdout.write('[1/7] Verificando banco de dados...')
        self.check_database()

        self.stdout.write('[2/7] Criando/atualizando usuário administrador...')
        self.create_admin_user()

        self.stdout.write('[3/7] Criando cadastros padrão: Equipes...')
        self.create_equipes()

        self.stdout.write('[4/7] Criando cadastros padrão: Cliente, Equipamentos...')
        self.create_cliente_equipamentos()

        self.stdout.write('[5/7] Criando cadastros padrão: Tipo Problema, Atividade, Prioridade, Projetos, Solicitantes...')
        self.create_cadastros_auxiliares()

        self.stdout.write('[6/7] Criando cadastros padrão: Status do sistema...')
        self.create_status_sistema()

        self.stdout.write('[7/7] Validando dados...')
        self.validate_data()

        self.stdout.write(self.style.SUCCESS('\n[OK] Setup concluido com sucesso!'))

    def check_database(self):
        """Verifica se o banco está acessível."""
        from django.db import connection
        try:
            connection.ensure_connection()
            self.stdout.write(self.style.SUCCESS('  OK - Banco de dados acessível'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ERRO - Não foi possível conectar ao banco: {e}'))
            raise

    def create_admin_user(self):
        """Cria ou atualiza o usuário administrador."""
        email = 'admin@semeq.com'
        password = os.environ.get('ADMIN_PASSWORD')
        if not password:
            import warnings
            warnings.warn('ADMIN_PASSWORD não definido no .env - usando fallback inseguro!', RuntimeWarning)
            password = 'Semeq@123'

        # Remove duplicatas se houver - reatribuir objetos relacionados ao primeiro
        admins = User.objects.filter(email=email)
        if admins.count() > 1:
            # Manter apenas o primeiro (menor ID), reatribuir relacionados aos outros
            admins_ordered = admins.order_by('id')
            primeiro = admins_ordered.first()
            for admin in admins_ordered.exclude(id=primeiro.id):
                # Reatribuir Apontamentos
                from user.models import Apontamento, ApontamentoTempo
                Apontamento.objects.filter(responsavel=admin).update(responsavel=primeiro)
                Apontamento.objects.filter(criado_por=admin).update(criado_por=primeiro)
                ApontamentoTempo.objects.filter(responsavel=admin).update(responsavel=primeiro)
                ApontamentoTempo.objects.filter(criado_por=admin).update(criado_por=primeiro)
                # Deletar perfil do duplicado se existir
                if hasattr(admin, 'perfil'):
                    admin.perfil.delete()
                admin.delete()
                self.stdout.write(self.style.WARNING(f'  Removido admin duplicado (ID: {admin.id}) - objetos reatribuídos'))
            admin = primeiro
        elif admins.count() == 1:
            admin = admins.first()
        else:
            admin = None

        if admin:
            # Atualiza se necessário
            changed = False
            if not admin.is_superuser:
                admin.is_superuser = True
                changed = True
            if not admin.is_staff:
                admin.is_staff = True
                changed = True
            if admin.username != email:
                admin.username = email
                changed = True
            if changed:
                admin.save()
            admin.set_password(password)
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'  Admin atualizado: {email}'))
        else:
            admin = User.objects.create_superuser(
                username=email,
                email=email,
                password=password,
                first_name='Administrador',
            )
            admin.is_staff = True
            admin.is_active = True
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'  Admin criado: {email}'))

        # Garantir perfil
        PerfilUsuario.objects.update_or_create(
            user=admin,
            defaults={
                'role': 'admin',
                'ativo': True,
                'telefone': '',
            }
        )

    def create_equipes(self):
        """Cria equipes padrão."""
        equipes_padrao = [
            {'nome': 'PMC', 'ordem': 1},
        ]
        for eq_data in equipes_padrao:
            equipe, created = Equipe.objects.get_or_create(
                nome=eq_data['nome'],
                defaults={'ordem': eq_data['ordem'], 'ativo': True}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Equipe criada: {equipe.nome}'))
            else:
                self.stdout.write(f'  Equipe já existe: {equipe.nome}')

    def create_cliente_equipamentos(self):
        """Cria cliente padrão e equipamentos."""
        # Cliente
        cliente, created = Cliente.objects.get_or_create(
            corporation='SEMEQ',
            plant='LIMEIRA',
            defaults={'zone': '', 'ativo': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  Cliente criado: {cliente}'))
        else:
            self.stdout.write(f'  Cliente já existe: {cliente}')

        # Equipamentos
        equipamentos = [
            {'tipo': 'outro', 'device': 'Nenhum', 'modelo': ''},
            {'tipo': 'outro', 'device': 'Outro', 'modelo': ''},
        ]
        for eq_data in equipamentos:
            equipamento, created = Equipamento.objects.get_or_create(
                tipo=eq_data['tipo'],
                device=eq_data['device'],
                modelo=eq_data['modelo'],
                defaults={'ativo': True}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Equipamento criado: {equipamento}'))
            else:
                self.stdout.write(f'  Equipamento já existe: {equipamento}')

    def create_cadastros_auxiliares(self):
        """Cria cadastros auxiliares padrão."""
        # Tipo de Problema
        tp, created = TipoProblema.objects.get_or_create(
            nome='Teste',
            defaults={'ativo': True, 'ordem': 1, 'descricao': 'Tipo de problema para testes'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  Tipo Problema criado: {tp.nome}'))
        else:
            self.stdout.write(f'  Tipo Problema já existe: {tp.nome}')

        # Atividade
        atv, created = Atividade.objects.get_or_create(
            nome='Teste',
            defaults={'ativo': True, 'ordem': 1}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  Atividade criada: {atv.nome}'))
        else:
            self.stdout.write(f'  Atividade já existe: {atv.nome}')

        # Prioridade
        pr, created = Prioridade.objects.get_or_create(
            nome='Teste',
            defaults={'ativo': True, 'ordem': 1, 'cor': '#6c757d'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  Prioridade criada: {pr.nome}'))
        else:
            self.stdout.write(f'  Prioridade já existe: {pr.nome}')

        # Projetos
        proj, created = Projeto.objects.get_or_create(
            nome='PMC',
            defaults={'ativo': True, 'ordem': 1}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  Projeto criado: {proj.nome}'))
        else:
            self.stdout.write(f'  Projeto já existe: {proj.nome}')

        # Solicitantes
        sol, created = Solicitante.objects.get_or_create(
            nome='PMC',
            defaults={'ativo': True, 'ordem': 1}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  Solicitante criado: {sol.nome}'))
        else:
            self.stdout.write(f'  Solicitante já existe: {sol.nome}')

    def create_status_sistema(self):
        """Cria os 3 status fixos do sistema."""
        status_padrao = [
            {'status': 'Aberto', 'ordem': 1, 'cor': '#0d6efd', 'is_concluido': False},
            {'status': 'Executando', 'ordem': 2, 'cor': '#ffc107', 'is_concluido': False},
            {'status': 'Concluído', 'ordem': 3, 'cor': '#198754', 'is_concluido': True},
        ]
        for st_data in status_padrao:
            # Busca case-insensitive para nao duplicar ('aberto' vs 'Aberto')
            status = Status.objects.filter(status__iexact=st_data['status']).first()
            if status is None:
                status = Status.objects.create(
                    status=st_data['status'],
                    ordem=st_data['ordem'],
                    cor=st_data['cor'],
                    is_concluido=st_data['is_concluido'],
                    ativo=True,
                )
                self.stdout.write(self.style.SUCCESS(f'  Status criado: {status.status}'))
                continue
            # Normaliza existente para o canonico (nome, cor, ordem, is_concluido, ativo)
            changed = False
            for field in ('status', 'cor', 'ordem', 'is_concluido'):
                if getattr(status, field) != st_data[field]:
                    setattr(status, field, st_data[field])
                    changed = True
            if not status.ativo:
                status.ativo = True
                changed = True
            if changed:
                status.save()
                self.stdout.write(self.style.WARNING(f'  Status atualizado: {status.status}'))
            else:
                self.stdout.write(f'  Status já existe: {status.status}')

    def validate_data(self):
        """Valida se todos os dados obrigatórios existem."""
        errors = []
        warnings = []

        # Verifica admin
        if not User.objects.filter(email='admin@semeq.com', is_superuser=True).exists():
            errors.append('Usuário admin@semeq.com não encontrado ou não é superuser')

        # Verifica equipes
        if not Equipe.objects.filter(nome='PMC').exists():
            errors.append('Equipe PMC não encontrada')

        # Verifica cliente
        if not Cliente.objects.filter(corporation='SEMEQ', plant='LIMEIRA').exists():
            errors.append('Cliente SEMEQ LIMEIRA não encontrado')

        # Verifica equipamentos
        for eq_device in ['Outro', 'Nenhum']:
            if not Equipamento.objects.filter(device=eq_device).exists():
                errors.append(f'Equipamento "{eq_device}" não encontrado')

        # Verifica status
        for nome in ['Aberto', 'Executando', 'Concluído']:
            if not Status.objects.filter(status=nome).exists():
                errors.append(f'Status "{nome}" não encontrado')
            else:
                st = Status.objects.get(status=nome)
                if not st.is_fixo:
                    warnings.append(f'Status "{nome}" não está marcado como fixo')

        # Verifica cadastros auxiliares
        if not TipoProblema.objects.filter(nome='Teste').exists():
            errors.append('Tipo de Problema "Teste" não encontrado')
        if not Atividade.objects.filter(nome='Teste').exists():
            errors.append('Atividade "Teste" não encontrada')
        if not Prioridade.objects.filter(nome='Teste').exists():
            errors.append('Prioridade "Teste" não encontrada')
        if not Projeto.objects.filter(nome='PMC').exists():
            errors.append('Projeto "PMC" não encontrado')
        if not Solicitante.objects.filter(nome='PMC').exists():
            errors.append('Solicitante "PMC" não encontrado')

        if errors:
            for e in errors:
                self.stdout.write(self.style.ERROR(f'  ERRO: {e}'))
            raise Exception('Validação falhou - verifique erros acima')

        for w in warnings:
            self.stdout.write(self.style.WARNING(f'  AVISO: {w}'))

        self.stdout.write(self.style.SUCCESS('  Validação OK - Todos os cadastros obrigatórios existem'))