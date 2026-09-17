import unicodedata
import re
from django.core.management.base import BaseCommand
from user.models import Cliente


def sanitize_text(text: str) -> str:
    """Normalize and clean text using NFKC."""
    if not text:
        return ''
    # Normalize unicode characters
    text = unicodedata.normalize('NFKC', text)
    # Replace common problematic characters
    replacements = {
        '\u2013': '-',  # en-dash
        '\u2014': '-',  # em-dash
        '\u2018': "'",  # left single quote
        '\u2019': "'",  # right single quote
        '\u201c': '"',  # left double quote
        '\u201d': '"',  # right double quote
        '\u2026': '...', # ellipsis
        '\u00a0': ' ',  # non-breaking space
        '\u00b7': '-',  # middle dot
        '\u2022': '-',  # bullet
        '\u25aa': '-',  # black small square
        '\u25cf': '-',  # black circle
        '\u0096': '-',  # START OF GUARDED AREA (control char)
        '\u0097': '-',  # END OF GUARDED AREA (control char)
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Remove any remaining control characters (except newline/tab)
    text = re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]', '', text)
    return text.strip()


class Command(BaseCommand):
    help = 'Sanitiza caracteres especiais nos clientes (corporation, plant, zone, plant_id)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria alterado sem salvar',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limite de registros para processar (0 = todos)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        
        qs = Cliente.objects.all()
        if limit:
            qs = qs[:limit]
        
        total = qs.count()
        alterados = 0
        
        self.stdout.write(f'Processando {total} clientes...')
        
        for cliente in qs:
            original_corp = cliente.corporation
            original_plant = cliente.plant
            original_zone = cliente.zone
            original_plant_id = cliente.plant_id
            
            # Sanitize each field
            new_corp = sanitize_text(original_corp)
            new_plant = sanitize_text(original_plant)
            new_zone = sanitize_text(original_zone)
            new_plant_id = sanitize_text(original_plant_id)
            
            # Check if any field changed
            changed = False
            changes = []
            
            if new_corp != original_corp:
                changes.append(f'corporation: "{original_corp}" -> "{new_corp}"')
                changed = True
            if new_plant != original_plant:
                changes.append(f'plant: "{original_plant}" -> "{new_plant}"')
                changed = True
            if new_zone != original_zone:
                changes.append(f'zone: "{original_zone}" -> "{new_zone}"')
                changed = True
            if new_plant_id != original_plant_id:
                changes.append(f'plant_id: "{original_plant_id}" -> "{new_plant_id}"')
                changed = True
            
            if changed:
                alterados += 1
                if dry_run:
                    # Use ascii-safe representation for console output
                    safe_changes = []
                    for ch in changes:
                        safe_changes.append(ch.encode('ascii', 'replace').decode())
                    self.stdout.write(f'  [DRY-RUN] Cliente #{cliente.pk}: {"; ".join(safe_changes)}')
                else:
                    cliente.corporation = new_corp
                    cliente.plant = new_plant
                    cliente.zone = new_zone
                    cliente.plant_id = new_plant_id
                    cliente.save(update_fields=['corporation', 'plant', 'zone', 'plant_id'])
                    safe_changes = []
                    for ch in changes:
                        safe_changes.append(ch.encode('ascii', 'replace').decode())
                    self.stdout.write(f'  [OK] Cliente #{cliente.pk}: {"; ".join(safe_changes)}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\nDRY-RUN: {alterados} de {total} clientes seriam alterados.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nConcluído: {alterados} de {total} clientes sanitizados.')
            )