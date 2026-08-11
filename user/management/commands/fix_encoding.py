from django.core.management.base import BaseCommand
from user.models import Cliente, Equipamento, Apontamento


MODEL_FIELDS = {
    Cliente: ['corporation', 'corporation_id', 'plant', 'plant_id', 'unat', 'city',
              'state_province', 'country', 'region', 'business', 'zone'],
    Equipamento: ['numero_serie', 'modelo', 'descricao', 'tipo'],
    Apontamento: ['projeto', 'solicitante', 'ticket', 'descricao'],
}


def fix_string(value):
    """
    Corrige encoding: caracteres C1 (U+0080–U+009F) armazenados como bytes
    Latin-1/CP1252 são re-mapeados para seus equivalentes Unicode via cp1252.

    Ex: '\x96' (en-dash em cp1252) vira '–' (U+2013).
    Letras acentuadas (U+00A0+) já são válidas e não são alteradas.
    Strings que não podem ser re-codificadas (já UTF-8) retornam inalteradas.
    """
    if not value:
        return value
    try:
        fixed = value.encode('latin-1').decode('cp1252')
        return fixed if fixed != value else value
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


class Command(BaseCommand):
    help = 'Corrige encoding latin-1/cp1252 em Cliente, Equipamento e Apontamento.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Apenas mostra o que mudaria, sem salvar.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        total_fields = 0
        total_registros = 0

        for model, fields in MODEL_FIELDS.items():
            for obj in model.objects.all().iterator():
                changes = {}
                for field_name in fields:
                    original = getattr(obj, field_name, None)
                    if not original:
                        continue
                    fixed = fix_string(original)
                    if fixed != original:
                        changes[field_name] = (original, fixed)
                if changes:
                    total_registros += 1
                    for field_name, (orig, fx) in changes.items():
                        total_fields += 1
                        if dry_run or options['verbosity'] >= 2:
                            self.stdout.write(
                                f'{model.__name__}#{obj.pk} .{field_name}:\n'
                                f'    ANTES  {orig!r}\n'
                                f'    DEPOIS {fx!r}'
                            )
                    if not dry_run:
                        for field_name, (_, fx) in changes.items():
                            setattr(obj, field_name, fx)
                        obj.save(update_fields=list(changes.keys()))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY-RUN] {total_fields} campo(s) em {total_registros} registro(s) seriam alterados.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{total_fields} campo(s) corrigidos em {total_registros} registro(s).'
            ))