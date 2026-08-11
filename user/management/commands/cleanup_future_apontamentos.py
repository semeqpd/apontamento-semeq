from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from user.models import Apontamento


class Command(BaseCommand):
    help = 'Remove apontamentos com data futura (maior que hoje).'

    def handle(self, *args, **options):
        hoje = date.today()
        qs = Apontamento.objects.filter(data__gt=hoje)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'{count} apontamento(s) futuro(s) removido(s) (data > {hoje.isoformat()}).'
        ))