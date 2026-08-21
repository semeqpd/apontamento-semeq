from django.core.management.base import BaseCommand
from user.models import Cliente, Equipamento, Apontamento
import re


MODEL_FIELDS = {
    Cliente: ['corporation', 'corporation_id', 'plant', 'plant_id', 'unat', 'city',
              'state_province', 'country', 'region', 'business', 'zone'],
    Equipamento: ['numero_serie', 'modelo', 'descricao', 'tipo'],
    Apontamento: ['projeto', 'solicitante', 'ticket', 'descricao'],
}


def fix_string(value):
    if not value:
        return value
    
    import re
    
    try:
        fixed = value.encode('latin-1').decode('cp1252')
        if fixed != value:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    
    try:
        latin1_bytes = value.encode('latin-1')
        fixed = latin1_bytes.decode('utf-8')
        if fixed != value:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    
    if '\ufffd' in value:
        try:
            for continuation_byte in range(0x80, 0xA0):
                test_value = value.replace('\ufffd', chr(continuation_byte))
                try:
                    test_bytes = test_value.encode('latin-1')
                    fixed = test_bytes.decode('utf-8')
                    if fixed != value and not any(ord(c) in range(0x80, 0xA0) for c in fixed):
                        return fixed
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue
        except:
            pass
    
    c1_to_accented = {
        '\u00c3\x81': 'A', '\u00c3\x82': 'A', '\u00c3\x83': 'A', '\u00c3\x84': 'A',
        '\u00c3\x85': 'A', '\u00c3\x86': 'AE', '\u00c3\x87': 'C', '\u00c3\x88': 'E',
        '\u00c3\x89': 'E', '\u00c3\x8a': 'E', '\u00c3\x8b': 'E', '\u00c3\x8c': 'I',
        '\u00c3\x8d': 'I', '\u00c3\x8e': 'I', '\u00c3\x8f': 'I', '\u00c3\x90': 'D',
        '\u00c3\x91': 'N', '\u00c3\x92': 'O', '\u00c3\x93': 'O', '\u00c3\x94': 'O',
        '\u00c3\x95': 'O', '\u00c3\x96': 'O', '\u00c3\x97': 'X', '\u00c3\x98': 'O',
        '\u00c3\x99': 'U', '\u00c3\x9a': 'U', '\u00c3\x9b': 'U', '\u00c3\x9c': 'U',
        '\u00c3\x9d': 'Y', '\u00c3\x9e': 'TH', '\u00c3\x9f': 'SS',
        '\u00c3\xa1': 'a', '\u00c3\xa2': 'a', '\u00c3\xa3': 'a', '\u00c3\xa4': 'a',
        '\u00c3\xa5': 'a', '\u00c3\xa6': 'ae', '\u00c3\xa7': 'c', '\u00c3\xa8': 'e',
        '\u00c3\xa9': 'e', '\u00c3\xaa': 'e', '\u00c3\xab': 'e', '\u00c3\xac': 'i',
        '\u00c3\xad': 'i', '\u00c3\xae': 'i', '\u00c3\xaf': 'i', '\u00c3\xb0': 'd',
        '\u00c3\xb1': 'n', '\u00c3\xb2': 'o', '\u00c3\xb3': 'o', '\u00c3\xb4': 'o',
        '\u00c3\xb5': 'o', '\u00c3\xb6': 'o', '\u00c3\xb7': 'X', '\u00c3\xb8': 'o',
        '\u00c3\xb9': 'u', '\u00c3\xba': 'u', '\u00c3\xbb': 'u', '\u00c3\xbc': 'u',
        '\u00c3\xbd': 'y', '\u00c3\xbe': 'TH', '\u00c3\xbf': 'y',
    }
    pattern = '|'.join(re.escape(k) for k in c1_to_accented.keys())
    fixed = re.sub(pattern, lambda m: c1_to_accented.get(m.group(0), m.group(0)), value)
    if fixed != value:
        return fixed
    
    try:
        latin1_bytes = value.encode('latin-1')
        fixed = latin1_bytes.decode('utf-8')
        if fixed != value:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    
    if '\ufffd' in value:
        try:
            for continuation_byte in range(0x80, 0xA0):
                test_value = value.replace('\ufffd', chr(continuation_byte))
                try:
                    test_bytes = test_value.encode('latin-1')
                    fixed = test_bytes.decode('utf-8')
                    if fixed != value and not any(ord(c) in range(0x80, 0xA0) for c in fixed):
                        return fixed
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue
        except:
            pass
    
    mojibake_map = {
        '\u00c3A': 'A', '\u00c3a': 'a',
        '\u00c3E': 'E', '\u00c3e': 'e',
        '\u00c3I': 'I', '\u00c3i': 'i',
        '\u00c3O': 'O', '\u00c3o': 'o',
        '\u00c3U': 'U', '\u00c3u': 'u',
        '\u00c3C': 'C', '\u00c3c': 'c',
    }
    pattern = '|'.join(re.escape(k) for k in mojibake_map.keys())
    fixed = re.sub(pattern, lambda m: mojibake_map.get(m.group(0), m.group(0)), value)
    if fixed != value:
        return fixed
    
    try:
        fixed = value.replace('\u00c3?', '\u00d3')
        if fixed != value:
            return fixed
    except:
        pass
    
    smart_quote_map = {
        '\u00c3?': '\u00d3',
    }
    for bad, good in smart_quote_map.items():
        if bad in value:
            return value.replace(bad, good)

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
