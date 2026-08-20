# The mojibake: UTF-8 bytes interpreted as latin-1
# Original 'Ó' = UTF-8 bytes C3 93
# When read as latin-1: C3 = Ã (U+00C3), 93 = " (U+201D or control)

# Current mojibake string
s = 'PETRÃOLEO'
print('Current:', repr(s))

# Fix: encode as latin-1 to get bytes, then decode as UTF-8
try:
    fixed = s.encode('latin-1').decode('utf-8')
    print('Fixed:', repr(fixed))
except Exception as e:
    print('Error:', e)

# Test with the actual problematic char
s2 = 'IPIRANGA PETRÃOLEO'
print('Original:', repr(s2))
try:
    fixed2 = s2.encode('latin-1').decode('utf-8')
    print('Fixed2:', repr(fixed2))
except Exception as e:
    print('Error:', e)