# Heuristic fix for common Portuguese mojibake patterns
# The character Ã is U+00C3

MOJIBAKE_MAP = {
    '\u00c3A': 'Á', '\u00c3a': 'á',
    '\u00c3E': 'É', '\u00c3e': 'é',
    '\u00c3I': 'Í', '\u00c3i': 'í',
    '\u00c3O': 'Ó', '\u00c3o': 'ó',
    '\u00c3U': 'Ú', '\u00c3u': 'ú',
    '\u00c3C': 'Ç', '\u00c3c': 'ç',
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

print("=== Heuristic Portuguese Mojibake Fix (Unicode) ===")
for case in test_cases:
    fixed = fix_portuguese_mojibake(case)
    print(f'{case} -> {fixed}')