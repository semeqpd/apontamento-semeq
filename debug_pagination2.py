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

# Check CSS classes on pagination
import re
matches = re.findall(r'class="[^"]*pagination[^"]*"', content)
for m in re.finditer(r'class="[^"]*pagination[^"]*"', content):
    print(f'Pagination class: {m.group()}')

# Check for d-none classes on pagination
matches = re.findall(r'class="[^"]*d-none[^"]*"', content)
for m in re.finditer(r'class="[^"]*d-none[^"]*"', content):
    print(f'Found d-none: {m.group()}')

# Check for d-sm-none, d-md-none, etc.
for pattern in ['d-sm-none', 'd-md-none', 'd-lg-none', 'd-xl-none', 'd-xxl-none', 'd-none d-sm-block', 'd-none d-md-block', 'd-none d-lg-block', 'd-none d-xl-block']:
    if pattern in content:
        print(f'Found {pattern} in HTML')

# Check pagination HTML
for line in content.split('\n'):
    if 'pagination' in line.lower() or 'page-item' in line.lower() or 'page-link' in line.lower():
        print(f'  {line.strip()[:200]}')