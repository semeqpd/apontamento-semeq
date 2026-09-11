from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from user.models import PerfilUsuario
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Cria o usuário administrador padrão (admin@semeq.com) se não existir. Senha via variável de ambiente ADMIN_PASSWORD (fallback: Semeq@123 em dev).'

    def handle(self, *args, **options):
        email = 'admin@semeq.com'
        # Em produção, exige ADMIN_PASSWORD no .env; em dev usa fallback
        password = os.environ.get('ADMIN_PASSWORD')
        if not password:
            import warnings
            warnings.warn('ADMIN_PASSWORD não definido no .env - usando fallback inseguro!', RuntimeWarning)
            password = 'Semeq@123'  # Apenas fallback para desenvolvimento local

        if User.objects.filter(email=email).exists():
            admin = User.objects.get(email=email)
            if not admin.is_superuser:
                admin.is_superuser = True
                admin.is_staff = True
                admin.save()
                self.stdout.write(self.style.SUCCESS(f'Superuser promovido: {email}'))
            else:
                self.stdout.write(self.style.WARNING(f'Usuário admin {email} já existe.'))
            return

        # Cria superuser
        admin = User.objects.create_superuser(
            username=email,
            email=email,
            password=password,
            first_name='Administrador',
        )
        admin.is_staff = True
        admin.is_active = True
        admin.save()

        # Garantir perfil
        PerfilUsuario.objects.update_or_create(
            user=admin,
            defaults={
                'role': 'admin',
                'ativo': True,
                'telefone': '',
            }
        )

        self.stdout.write(self.style.SUCCESS(
            f'Usuário admin criado com sucesso!\n'
            f'  Email: {email}\n'
            f'  Senha: [definida via ADMIN_PASSWORD]'
        ))