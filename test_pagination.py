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
    print(f'  {status} {name}')