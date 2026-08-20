import re

MOJIBAKE_MAP = {
    '\u00c3A': 'Á', '\u00c3a': 'á',
    '\u00c3E': 'É', '\u00c3e': 'é',
    '\u00c3I': 'Í', '\u00c3i': 'í',
    '\u00c3O': 'Ó', '\u00c3o': 'ó',
    '\u00c3U': 'Ú', '\u00c3u': 'ú',
    '\u00c3C': 'Ç', '\u00c3c': 'ç',
}

patterns = sorted(MOJIBAKE_MAP.keys(), key=len, reverse=True)
pattern = '|'.join(re.escape(k) for k in MOJIBAKE_MAP.keys())

def fix_mojibake(text):
    if not text:
        return text
    def replacer(m):
        return MOJIBAKE_MAP.get(m.group(0), m.group(0))
    return re.sub('|'.join(re.escape(k) for k in MOJIBAKE_MAP.keys()), lambda m: MOJIBAKE_MAP.get(m.group(0), m.group(0)), text)

# Test with actual mojibake strings
test_cases = [
    'PETRÃOLEO',
    'IPIRANGA PETRÃOLEO',
    'SÃO PAULO',
    'UNIÃO',
    'CORAÇÃO',
    'MÚSICA',
]

print("=== Test with actual mojibake strings ===")
for t in test_cases:
    print(f"Input bytes: {[hex(ord(c)) for c in t]}")
    fixed = re.sub('|'.join(re.escape(k) for k in {'\u00c3A':1,'\u00c3a':1,'\u00c3E':1,'\u00c3e':1,'\u00c3I':1,'\u00c3i':1,'\u00c3O':1,'\u00c3o':1,'\u00c3U':1,'\u00c3u':1,'\u00c3C':1,'\u00c3c':1}.keys()), lambda m: {'\u00c3A':'Á','\u00c3a':'á','\u00c3E':'É','\u00c3e':'é','\u00c3I':'Í','\u00c3i':'í','\u00c3O':'Ó','\u00c3o':'ó','\u00c3U':'Ú','\u00c3u':'ú','\u00c3C':'Ç','\u00c3c':'ç'}.get(m.group(0), m.group(0)), t)
    print(f'{t} -> {fixed}')
    print()