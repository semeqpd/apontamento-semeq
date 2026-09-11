from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from user.models import PerfilUsuario, Equipe

User = get_user_model()

# Estrutura de usuários: admin+gestor globais, líderes e colaboradores por equipe
USUARIOS = [
    # (username, first_name, email, role, equipe_nome)
    ('admin', 'Administrador', 'admin@semeq.com', 'admin', None),
    ('gestor', 'Gestor', 'gestor@semeq.com', 'gestor', None),
    # Equipe PMC
    ('lider_pmc', 'Líder PMC', 'lider.pmc@semeq.com', 'lider', 'PMC'),
    ('colab_pmc1', 'Colaborador PMC 1', 'colab1.pmc@semeq.com', 'colaborador', 'PMC'),
    ('colab_pmc2', 'Colaborador PMC 2', 'colab2.pmc@semeq.com', 'colaborador', 'PMC'),
    ('colab_pmc3', 'Colaborador PMC 3', 'colab3.pmc@semeq.com', 'colaborador', 'PMC'),
    # Equipe SHD
    ('lider_shd', 'Líder SHD', 'lider.shd@semeq.com', 'lider', 'SHD'),
    ('colab_shd1', 'Colaborador SHD 1', 'colab1.shd@semeq.com', 'colaborador', 'SHD'),
    ('colab_shd2', 'Colaborador SHD 2', 'colab2.shd@semeq.com', 'colaborador', 'SHD'),
    ('colab_shd3', 'Colaborador SHD 3', 'colab3.shd@semeq.com', 'colaborador', 'SHD'),
]

SENHA = 'Semeq@123'


class Command(BaseCommand):
    help = 'Remove usuários existentes e cria a estrutura padrão de usuários/times (PMC e SHD).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only-if-missing',
            action='store_true',
            help='Pula tudo se o usuário admin (ou qualquer usuário do sistema) já existir.',
        )

    def handle(self, *args, **options):
        # Modo idempotente p/ Docker: não sobrescreve banco já populado
        if options.get('only_if_missing'):
            if User.objects.filter(username__in=[u[0] for u in USUARIOS]).exists():
                self.stdout.write(self.style.WARNING(
                    'Usuários do sistema já existem. Pulando setup_usuarios (--only-if-missing).'
                ))
                return

        # 0. Garantir que existe um usuário admin reserva para reassignar apontamentos
        admin_reserva, _ = User.objects.get_or_create(
            username='__system__',
            defaults={'is_active': False}
        )
        usuarios_sistema = [u[0] for u in USUARIOS]

        # 1. Reassignar apontamentos de usuários que serão removidos (FK PROTECT)
        from user.models import Apontamento
        for u in User.objects.all():
            if u.username in usuarios_sistema or u.username == admin_reserva.username:
                continue
            Apontamento.objects.filter(responsavel=u).update(responsavel=admin_reserva)
            Apontamento.objects.filter(criado_por=u).update(criado_por=admin_reserva)

        # 2. Remover usuários que serão recriados (com segurança se não houver refs)
        for username in usuarios_sistema:
            try:
                User.objects.filter(username=username).delete()
            except Exception:
                # Se ainda houver refs, move para reserva e tenta de novo
                Apontamento.objects.filter(responsavel__username=username).update(responsavel=admin_reserva)
                Apontamento.objects.filter(criado_por__username=username).update(criado_por=admin_reserva)
                User.objects.filter(username=username).delete()

        # 3. Garantir Equipes PMC e SHD
        equipes = {}
        for nome in ['PMC', 'SHD']:
            equipe, _ = Equipe.objects.update_or_create(
                nome=nome,
                defaults={'ativo': True}
            )
            equipes[nome] = equipe
        self.stdout.write(self.style.SUCCESS('Equipes PMC e SHD criadas.'))

        # 4. Criar usuários
        for username, first_name, email, role, equipe_nome in USUARIOS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'email': email,
                    'is_active': True,
                    'is_staff': role == 'admin' or username == 'admin',
                }
            )
            if not created:
                user.first_name = first_name
                user.email = email
                user.is_active = True
                user.is_staff = role == 'admin' or username == 'admin'
            user.set_password(SENHA)
            user.save()

            equipe = equipes.get(equipe_nome) if equipe_nome else None
            PerfilUsuario.objects.update_or_create(
                user=user,
                defaults={
                    'role': role,
                    'equipe': equipe,
                    'ativo': True,
                    'telefone': '',
                }
            )
            self.stdout.write(self.style.SUCCESS(
                f'  {username} -> {role}{(" / " + equipe_nome) if equipe_nome else " (global)"}'
            ))

        # 5. Garantir admin global superuser
        admin = User.objects.filter(username='admin').first()
        if admin and not admin.is_superuser:
            admin.is_superuser = True
            admin.is_staff = True
            admin.save()

        # 6. Reassignar apontamentos do usuário reserva de volta para o admin
        Apontamento.objects.filter(responsavel=admin_reserva).update(responsavel=admin)
        Apontamento.objects.filter(criado_por=admin_reserva).update(criado_por=admin)
        admin_reserva.delete()

        self.stdout.write(self.style.SUCCESS(
            f'\nSetup concluído. {len(USUARIOS)} usuários. Senha padrão: {SENHA}'
        ))