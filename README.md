# Portal SEMEQ - Sistema de Apontamentos

Sistema web em Django para registro de apontamentos de horas e atendimentos. Permite criar, editar e acompanhar apontamentos, controlar quem os registrou, gerenciar clientes e usuários, e gerar relatórios em CSV/Excel.

## Funcionalidades

- Registro de apontamentos de horas (criação, edição, exclusão, status e exportação).
- Dashboard com indicadores e filtros por equipe, colaborador, status, prioridade e data.
- Gestão de clientes (cadastro e importação de Excel/CSV).
- Gestão de usuários com papéis e times.
- Tema claro/escuro.

## Como rodar

Requisitos: Python 3.12+ e PostgreSQL (ou SQLite, sem instalação extra).

### 1. Clonar e entrar no projeto

```bash
git clone <url-do-repositorio>.git
cd apontamento-semeq
git checkout teste
```

### 2. Criar e ativar o ambiente virtual

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS
```

### 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar o ambiente (`.env`)

Crie um arquivo `.env` na raiz do projeto e defina as variáveis (não são versionadas):

```
DJANGO_SECRET_KEY=<gerar com get_random_secret_key>
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Banco de dados
DJANGO_DB_ENGINE=postgres
DJANGO_DB_NAME=apontamento
DJANGO_DB_USER=<usuario>
DJANGO_DB_PASSWORD=<senha>
DJANGO_DB_HOST=localhost
DJANGO_DB_PORT=5432
```

### 5. Criar o banco no PostgreSQL (uma vez)

No `psql` do banco, crie o usuário e o banco:

```sql
CREATE ROLE <usuario> WITH LOGIN PASSWORD '<senha>' SUPERUSER CREATEDB;
CREATE DATABASE apontamento OWNER <usuario>;
```

### 6. Aplicar as migrações

```bash
python manage.py migrate
```

### 7. Criar os usuários iniciais

```bash
python manage.py setup_usuarios
```

### 8. Rodar o servidor

```bash
python manage.py runserver 0.0.0.0:8000
```

Acesse `http://127.0.0.1:8000/`.