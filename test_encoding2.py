# Test the _fix_encoding approach
def fix_encoding(value):
    if not value:
        return value
    try:
        fixed = value.encode('latin-1').decode('cp1252')
        return fixed if fixed != value else value
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value

# Test cases
test_cases = [
    'PETRÃOLEO',
    'IPIRANGA PETRÃOLEO',
    'PETRÓLEO',  # already correct
    'São Paulo',
    'BAIXA GRANDE DO RIBEIRO/PI',
]

for case in test_cases:
    fixed = fix_encoding(case)
    print(f'Original: {repr(case)}')
    print(f'Fixed:  {repr(fixed)}')
    print()