# Heuristic fix for common Portuguese mojibake patterns
# Pattern: Ã (U+00C3) followed by vowel/C -> accented character

import re

# Mapping of mojibake patterns to correct characters
# Pattern: Ã + letter -> accented character
MOJIBAKE_MAP = {
    'ÃA': 'Á', 'Ãa': 'á',
    'ÃE': 'É', 'Ãe': 'é',
    'ÃI': 'Í', 'Ãi': 'í',
    'ÃO': 'Ó', 'Ão': 'ó',
    'ÃU': 'Ú', 'Ãu': 'ú',
    'ÃC': 'Ç', 'Ãc': 'ç',
    'Ã ': 'Á ',  # edge case
}

# Build regex pattern
pattern = '|'.join(re.escape(k) for k in MOJIBAKE_MAP.keys())
# Sort by length descending to match longer patterns first
pattern = '|'.join(sorted([re.escape(k) for k in MOJIBAKE_MAP.keys()], key=len, reverse=True))

def fix_portuguese_mojibake(text):
    """Fix common Portuguese mojibake patterns"""
    if not text:
        return text
    
    def replace_match(match):
        return MOJIBAKE_MAP.get(match.group(0), match.group(0))
    
    return re.sub(pattern, replace_match, text)

# Test
test_cases = [
    'PETRÃOLEO',
    'IPIRANGA PETRÃOLEO',
    'PETRÓLEO',
    'São Paulo',
    'BAIXA GRANDE DO RIBEIRO/PI',
    'SÃO PAULO',
    'UNIÃO',
    'CORAÇÃO',
    'MÚSICA',
]

print("=== Heuristic Portuguese Mojibake Fix ===")
for case in test_cases:
    fixed = fix_portuguese_mojibake(case)
    print(f'{case} -> {fixed}')