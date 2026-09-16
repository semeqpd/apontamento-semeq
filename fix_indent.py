with open('user/forms.py', 'rb') as f:
    content = f.read()

# Fix the indentation issue - ensure clean_email is properly indented
content = content.replace(
    b"            self.fields['ativo'].disabled = True\r\n    \r\n    def clean_email(self):",
    b"            self.fields['ativo'].disabled = True\r\n\r\n    def clean_email(self):"
)

with open('user/forms.py', 'wb') as f:
    f.write(content)
print('Fixed')