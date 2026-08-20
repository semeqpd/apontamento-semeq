# -*- coding: utf-8 -*-
# Heuristic fix for common Portuguese mojibake patterns
# Mojibake: UTF-8 bytes C3 93 (Ó) read as latin-1 -> Ã (U+00C3) + " (U+201D)
# But in Python, the string shows as: PETRÃOLEO where Ã = U+00C3 and " = U+201D

# The actual pattern: U+00C3 (Ã) followed by A/E/I/O/U/C
MOJIBAKE_MAP = {
    '\u00c3A': 'Á',  # Ã + A -> Á
    '\u00c3a': 'á',  # Ã + a -> á
    '\u00c3E': 'É',
    '\u00c3e': 'é',
    '\u00c3I': 'Í',
    '\u00c3i': 'í',
    '\u00c3O': 'Ó',
    '\u00c3o': 'ó',
    '\u00c3U': 'Ú',
    '\u00c3u': 'ú',
    '\u00c3C': 'Ç',
    '\u00c3c': 'ç',
}

import re

# Sort keys by length descending (longer first)
patterns = sorted(MOJIBAKE_MAP.keys(), key=len, reverse=True)
pattern = '|'.join(re.escape(k) for k in patterns)

def fix_portuguese_mojibake(text):
    if not text:
        return text
    
    def replace_match(match):
        return MOJIBAKE_MAP.get(match.group(0), match.group(0))
    
    return re.sub(pattern, replace_match, text)

# Test with explicit Unicode code points
test_cases = [
    'PETR\u00c3OLEO',        # PETRÃOLEO
    'IPIRANGA PETR\u00c3OLEO', # IPIRANGA PETRÃOLEO
    'PETR\u00d3LEO',         # PETRÓLEO (already correct)
    'S\u00e3o Paulo',        # São Paulo
    'BAIXA GRANDE DO RIBEIRO/PI',
    'S\u00c3O PAULO',        # SÃO PAULO
    'UNI\u00c3O',            # UNIÃO
    'CORA\u00c7\u00c3O',     # CORAÇÃO (Ç = \u00c7, Ã = \u00c3, O = O)
    'M\u00faSICA',           # MÚSICA
]

print("=== Heuristic Portuguese Mojibake Fix ===")
for case in test_cases:
    def fix_portuguese_mojibake(text):
        if not text:
            return text
        def replace_match(match):
            return MOJIBAKE_MAP.get(match.group(0), match.group(0))
        return re.sub(pattern, replace_match, text)
    
    fixed = fix_portuguese_mojibake(case)
    print(f'{case} -> {fixed}')

print("Done")