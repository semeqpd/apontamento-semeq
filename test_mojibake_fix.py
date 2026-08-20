# Test the actual mojibake pattern
# UTF-8 'Ó' = bytes C3 93
# When read as latin-1: C3 = Ã (U+00C3), 93 = " (U+201D or control)

# The ACTUAL mojibake strings in the XLSX:
# PETRÓLEO -> UTF-8 bytes C3 93 -> latin-1 misread -> PETRÃ"
# But the user showed: PETRÃOLEO (with O, not ")
# So the actual data might be: UTF-8 C3 93 misread as latin-1 C3 83 + 4F? No...

# Let's test what happens when UTF-8 'Ó' (C3 93) is decoded as latin-1:
original = 'Ó'
utf8_bytes = original.encode('utf-8')  # b'\xc3\x93'
misread = utf8_bytes.decode('latin-1')  # Ã + "
print('Original:', original)
print('UTF-8 bytes:', utf8_bytes)
print('Misread as latin-1:', repr(misread))
print('Misread chars:', [hex(ord(c)) for c in misread])
print()

# Now test the fix: encode back to latin-1, decode as cp1252
fixed = misread.encode('latin-1').decode('cp1252')
print('Fixed:', repr(fixed))
print()

# Test with the actual mojibake strings the user is seeing
test_cases = [
    'PETRÃOLEO',        # User sees this (Ã + O)
    'IPIRANGA PETRÃOLEO',
    'SÃO PAULO',
    'UNIÃO',
    'CORAÇÃO',
]

# The fix: encode as latin-1, decode as cp1252
for case in test_cases:
    try:
        fixed = case.encode('latin-1').decode('cp1252')
    except:
        fixed = case
    print(f'{case} -> {fixed}')