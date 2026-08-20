# Test different encoding fix approaches
test_cases = [
    'PETRÃOLEO',
    'IPIRANGA PETRÃOLEO',
    'PETRÓLEO',
    'São Paulo',
    'BAIXA GRANDE DO RIBEIRO/PI',
]

print("=== Approach 1: latin-1 -> cp1252 (current _fix_encoding) ===")
for case in test_cases:
    try:
        fixed = case.encode('latin-1').decode('cp1252')
    except:
        fixed = case
    print(f'{case} -> {fixed}')

print("\n=== Approach 2: cp1252 -> utf-8 ===")
for case in test_cases:
    try:
        fixed = case.encode('cp1252').decode('utf-8')
    except:
        fixed = case
    print(f'{case} -> {fixed}')

print("\n=== Approach 3: utf-8 -> latin-1 ===")
for case in test_cases:
    try:
        fixed = case.encode('utf-8').decode('latin-1')
    except:
        fixed = case
    print(f'{case} -> {fixed}')

print("\n=== Approach 4: latin-1 -> utf-8 ===")
for case in test_cases:
    try:
        fixed = case.encode('latin-1').decode('utf-8')
    except:
        fixed = case
    print(f'{case} -> {fixed}')

print("\n=== Approach 5: cp1252 -> latin-1 ===")
for case in test_cases:
    try:
        fixed = case.encode('cp1252').decode('latin-1')
    except:
        fixed = case
    print(f'{case} -> {fixed}')

print("\n=== Approach 5: utf-8 -> cp1252 ===")
for case in test_cases:
    try:
        fixed = case.encode('utf-8').decode('cp1252')
    except:
        fixed = case
    print(f'{case} -> {fixed}')