with open('user/views.py', 'rb') as f:
    content = f.read()

# Normalize line endings
content = content.replace(b'\r\n', b'\n')

# Fix the indentation of get_context_data method - it's missing 4 spaces
old = b'\n            def get_context_data(self, **kwargs):'
new = b'\n    def get_context_data(self, **kwargs):'

if old in content:
    content = content.replace(old, new)
    print('Replaced')
else:
    print('Not found')

with open('user/views.py', 'wb') as f:
    f.write(content)
print('Done')