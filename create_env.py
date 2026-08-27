import os
from django.core.management.utils import get_random_secret_key

secret = get_random_secret_key()
with open('.env', 'w', encoding='utf-8') as f:
    f.write(f'DJANGO_SECRET_KEY={secret}\n')
    f.write('DJANGO_DEBUG=True\n')
    f.write('DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\n')
    f.write('\n')
    f.write('REM Para PostgreSQL, descomente e configure:\n')
    f.write('REM DJANGO_DB_ENGINE=postgres\n')
    f.write('REM DJANGO_DB_NAME=apontamento\n')
    f.write('REM DJANGO_DB_USER=admin\n')
    f.write('REM DJANGO_DB_PASSWORD=Semeq@2026abc\n')
    f.write('REM DJANGO_DB_HOST=localhost\n')
    f.write('REM DJANGO_DB_PORT=5432\n')
print('[OK] .env criado com SQLite (db.sqlite3).')