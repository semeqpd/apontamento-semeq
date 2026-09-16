from django.test import TestCase
from django.core.management import call_command

from user.models import Status
from user.forms import StatusForm


class FirstRunStatusTest(TestCase):
    """Garante que uma instalacao limpa cria exatamente os 3 status fixos."""

    def test_migrations_criam_exatamente_3_status(self):
        self.assertEqual(Status.objects.count(), 3)
        self.assertEqual(
            set(Status.objects.values_list('status', flat=True)),
            {'Aberto', 'Executando', 'Concluído'},
        )

    def test_setup_admin_mantem_3_status(self):
        call_command('setup_admin')
        self.assertEqual(Status.objects.count(), 3)
        canon = {s.status: (s.ordem, s.cor, s.is_concluido) for s in Status.objects.all()}
        self.assertEqual(canon['Aberto'], (1, '#0d6efd', False))
        self.assertEqual(canon['Executando'], (2, '#ffc107', False))
        self.assertEqual(canon['Concluído'], (3, '#198754', True))

    def test_form_bloqueia_duplicado_case_insensitive(self):
        form = StatusForm(data={
            'status': 'aberto', 'cor': '#000000', 'ordem': 9, 'ativo': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('status', form.errors)
