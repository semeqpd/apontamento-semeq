import csv
import openpyxl
from io import BytesIO


def parse_file(arquivo, ext: str):
    """Parse CSV or XLSX file and return headers and rows."""
    if ext == 'csv':
        content = arquivo.read().decode('utf-8-sig')
        reader = csv.reader(content.splitlines(), delimiter=';')
        headers = next(reader, [])
        rows = list(reader)
    elif ext in ('xlsx', 'xls'):
        wb = openpyxl.load_workbook(BytesIO(arquivo.read()))
        ws = wb.active
        headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            rows.append(list(row))
    else:
        raise ValueError(f'Formato não suportado: {ext}')
    return headers, rows


def normalize_row(row, headers):
    """Normalize row data to dict with header keys."""
    return {headers[i]: (row[i] if i < len(row) else '') for i in range(len(headers))}


def fix_encoding(text: str) -> str:
    """Fix common encoding issues."""
    if not text:
        return ''
    # Replace common encoding artifacts
    replacements = {
        'Ã§': 'ç', 'Ã£': 'ã', 'Ã©': 'é', 'Ã³': 'ó', 'Ã': 'à',
        'Ãª': 'ê', 'Ã´': 'ô', 'Ã­': 'í', 'Ãº': 'ú', 'Ã§': 'ç',
        'Ã‡': 'Ç', 'Ãƒ': 'Ã', 'Ã‰': 'É', 'Ã"': 'Ó', 'Ã': 'Á',
        'ÃŠ': 'Ê', 'Ã"': 'Ô', 'Ã': 'Í', 'Ãš': 'Ú', 'Ãœ': 'Ü',
    }
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
    return text.strip()