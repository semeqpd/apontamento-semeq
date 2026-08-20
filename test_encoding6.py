# -*- coding: utf-8 -*-
# Heuristic fix for common Portuguese mojibake patterns

MOJIBAKE_MAP = {
    'ÃA': 'Á', 'Ãa': 'á',
    'ÃE': 'É', 'Ãe': 'é',
    'ÃI': 'Í', 'Ãi': 'í',
    'ÃO': 'Ó', 'Ão': 'ó',
    'ÃU': 'Ú', 'Ãu': 'ú',
    'ÃC': 'Ç', 'Ãc': 'ç',
}

import re

# Sort keys by length descending
patterns = sorted(MOJIBAKE_MAP.keys(), key=len, reverse=True)
pattern = '|'.join(re.escape(k) for k in patterns)

def fix_portuguese_mojibake(text):
    if not text:
        return text
    
    def replace_match(match):
        return MOJIBAKE_MAP.get(match.group(0), match.group(0))
    
    return re.sub(pattern, replace_match, text)

# Test with explicit Unicode characters
# Ã = \u00c3
test_cases = [
    'PETR\u00c3OLEO',        # PETRÃOLEO
    'IPIRANGA PETR\u00c3OLEO', # IPIRANGA PETRÃOLEO
    'PETR\u00d3LEO',         # PETRÓLEO (correct)
    'S\u00e3o Paulo',        # São Paulo
    'BAIXA GRANDE DO RIBEIRO/PI',
    'S\u00c3O PAULO',        # SÃO PAULO
    'UNI\u00c3O',            # UNIÃO
    'CORA\u00c7\u00c3O',     # CORAÇÃO
    'M\u00faSICA',           # MÚSICA
]

print("=== Heuristic Portuguese Mojibake Fix ===")
for case in test_cases:
    # Build pattern dynamically from map keys
    import re
    patterns = sorted(MOJIBAKE_MAP.keys(), key=len, reverse=True)
    pattern = '|'.join(re.escape(k) for k in patterns)
    
    def fix_portuguese_mojibake(text):
        if not text:
            return text
        def replace_match(match):
            return MOJIBAKE_MAP.get(match.group(0), match.group(0))
        return re.sub(pattern, replace_match, text)
    
    fixed = fix_portuguese_mojibake(case)
    print(f'{case} -> {fixed}')

print("Done")