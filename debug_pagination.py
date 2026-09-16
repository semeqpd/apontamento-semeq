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

checks = [
    ('pagination nav', 'pagination' in content),
    ('ul pagination', '<ul class="pagination' in content),
    ('Previous link', 'bi-chevron-left' in content),
    ('Next link', 'bi-chevron-right' in content),
    ('Page numbers', 'page=' in content),
    ('Page 1 active', 'page-item active' in content),
    ('Results info', 'Mostrando' in content),
    ('Page numbers in href', 'page=1' in content or 'page=2' in content or 'page=3' in content),
]

print('Pagination checks:')
for name, result in checks:
    status = 'OK' if result else 'FAIL'
    print(f'  {"OK" if result else "FAIL"} {name}')

# Check pagination HTML
import re
navs = re.findall(r'<nav[^>]*>.*?</nav>', content, re.DOTALL)
print(f'\nFound {len(navs)} nav elements')
for i, nav in enumerate(re.findall(r'<nav[^>]*>.*?</nav>', content, re.DOTALL)):
    print(f'Nav {i}: {nav[:300]}...')

# Find page links
page_links = re.findall(r'href="[^"]*page=\d+', content)
print('\nPage links:', page_links[:10])

# Check for active page
active = re.search(r'page-item active', content)
print(f'\nActive page found: {bool(active)}')

# Show pagination HTML
for line in content.split('\n'):
    if 'pagination' in line.lower() or 'page-item' in line or 'page-link' in line:
        print(f'  {line.strip()[:200]}')