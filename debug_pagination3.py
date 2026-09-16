import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apontamento.settings')
import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
User = get_user_model()

client = Client()
user = User.objects.get(username='colab_pmc1')
client.force_login(user)

response = client.get('/apontamentos/')
response.render()
content = response.content.decode('utf-8')

# Check for inline styles hiding pagination
import re

# Check for inline styles on pagination
for line in content.split('\n'):
    if 'pagination' in line.lower() and ('style=' in line or 'd-none' in line or 'display:none' in line or 'visibility:hidden' in line or 'display: none' in line):
        print(f'Found potential hiding: {line.strip()[:200]}')

# Check the pagination HTML specifically
for line in content.split('\n'):
    if '<nav class="mt-4"' in line or '<ul class="pagination' in line:
        print(f'Found: {line.strip()[:300]}')
"