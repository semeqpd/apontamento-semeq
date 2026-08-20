# The fix works! The mojibake pattern is:
# UTF-8 'Ó' (C3 93) misread as latin-1 -> Ã (U+00C3) + " (U+0093)
# Fix: encode back to latin-1, decode as cp1252 -> 'Ó'

# But the user sees 'PETRÃOLEO' (with O not "). Let me check if there's another pattern.
# Maybe the data has been through multiple encoding steps.

# Test: what if the data was UTF-8 -> latin-1 -> then 0x93 replaced with O?
# Or maybe the data went through: UTF-8 -> latin-1 -> then some replacement

# Let me test the fix with the actual mojibake strings from the user's XLSX
# The fix works: encode('latin-1').decode('cp1252') works for the standard mojibake

# Now I need to also handle the case where the user sees Ã + O
# This could be: UTF-8 'Ó' (C3 93) -> some other encoding path

# Let me test the current _fix_encoding approach vs the new multi-strategy approach
# The current _fix_encoding does: latin-1 -> cp1252
# That's the correct fix for the standard mojibake!

# The user's test strings 'PETRÃOLEO' are NOT the actual mojibake - they're just examples
# The actual XLSX data has Ã + \x93 (or similar)

# The fix in _parse_file is correct - it applies _fix_encoding to XLSX values
# _fix_encoding does: encode('latin-1').decode('cp1252')

# Let me verify the fix works by testing with actual mojibake bytes
import re

def fix_mojibake(text):
    if not text:
        return text
    try:
        fixed = text.encode('latin-1', errors='replace').decode('cp1252')
        return fixed
    except:
        return text

# Test with actual mojibake (Ã + \x93)
test_mojibake = 'PETR\u00c3\x93LEO'  # This is the actual mojibake
print(f'Input: {repr(test_mojibake)}')
fixed = fix_mojibake(test_mojibake)
print(f'Fixed: {repr(fixed)}')
print()

# Also test the heuristic approach for cases where the mojibake has been partially "cleaned"
# e.g., if \x93 was replaced with O at some point
def fix_mojibake_heuristic(text):
    if not text:
        return text
    # Strategy 1: Standard mojibake fix (Ã + \x93 -> Ó)
    try:
        fixed = text.encode('latin-1', errors='replace').decode('cp1252')
        if fixed != text:
            return fixed
    except:
        pass
    # Strategy 2: Heuristic for Ã + vowel -> accented
    import re
    mojibake_map = {
        '\u00c3A': 'Á', '\u00c3a': 'á',
        '\u00c3E': 'É', '\u00c3e': 'é',
        '\u00c3I': 'Í', '\u00c3i': 'í',
        '\u00c3O': 'Ó', '\u00c3o': 'ó',
        '\u00c3U': 'Ú', '\u00c3u': 'ú',
        '\u00c3C': 'Ç', '\u00c3c': 'ç',
    }
    pattern = '|'.join(re.escape(k) for k in mojibake_map.keys())
    fixed = re.sub(pattern, lambda m: mojibake_map.get(m.group(0), m.group(0)), text)
    return fixed

# Test with user's example strings (which may have been partially cleaned)
test_cases = [
    'PETRÃOLEO',        # User sees this
    'IPIRANGA PETRÃOLEO',
    'SÃO PAULO',
    'UNIÃO',
    'CORAÇÃO',
    'PETRÓLEO',         # Already correct
    'São Paulo',
]

print("=== Testing heuristic fix ===")
for case in test_cases:
    fixed = fix_mojibake_heuristic(case)
    print(f'{case} -> {fixed}')