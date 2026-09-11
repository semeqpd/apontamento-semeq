# Portal SEMEQ - Sistema de Apontamentos

Sistema web em Django para registro de apontamentos de horas e atendimentos. Permite criar, editar e acompanhar apontamentos, controlar quem os registrou, gerenciar clientes e usuários, e gerar relatórios em CSV/Excel.

## Funcionalidades

- Registro de apontamentos de horas (criação, edição, exclusão, status e exportação).
- Dashboard com indicadores e filtros por equipe, colaborador, status, prioridade e data.
- Gestão de clientes (cadastro e importação de Excel/CSV).
- Gestão de usuários com papéis e times.
- Tema claro/escuro.
- Troca rápida de status via dropdown (lista de apontamentos).

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

# Email (opcional)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
ALLOWED_EMAIL_DOMAINS=semeq.com

# Senha do admin (obrigatório em produção)
ADMIN_PASSWORD=<senha-forte-para-o-admin>
```

### 5. Configurar o banco de dados PostgreSQL (uma vez)

> **Importante:** O usuário e a senha criados no banco **devem ser exatamente iguais** aos valores de `DJANGO_DB_USER` e `DJANGO_DB_PASSWORD` do `.env`. Escolha um par e use nos dois lugares.

Exemplo com o usuário `admin` e senha `senha123`:

No `.env`:
```
DJANGO_DB_USER=admin
DJANGO_DB_PASSWORD=senha123
```

No `psql` do banco:
```sql
CREATE ROLE admin WITH LOGIN PASSWORD 'senha123' SUPERUSER CREATEDB;
CREATE DATABASE apontamento OWNER admin;
```

> Você pode trocar `admin`/`senha123` por qualquer usuário/senha que preferir. O importante é que os valores no `.env` e no comando SQL sejam **os mesmos**.

### 6. Aplicar as migrações (ordem correta)

```bash
python manage.py migrate
```

> As migrações já incluem todas as alterações de modelo (tabelas de apontamentos, clientes, usuários, cadastros auxiliares, etc.). Rode **após** configurar o banco e o `.env`.

### 7. Criar usuário administrador padrão

```bash
python manage.py setup_admin
```

> Cria o superusuário `admin@semeq.com` (senha definida via variável de ambiente `ADMIN_PASSWORD` no `.env`). Em desenvolvimento, usa fallback `Semeq@123` se não definido.

### 8. (Opcional) Criar estrutura completa de usuários e equipes

```bash
python manage.py setup_usuarios
```

> Remove usuários existentes e cria a estrutura padrão:
> - **Admin global**: `admin` / `admin@semeq.com`
> - **Gestor global**: `gestor` / `gestor@semeq.com`
> - **Equipes**: PMC e SHD (com líderes e colaboradores)
> - **Senha padrão para todos**: `Semeq@123`
>
> Use `--only-if-missing` para pular se já existirem usuários:
> ```bash
> python manage.py setup_usuarios --only-if-missing
> ```

### 9. Rodar o servidor

```bash
python manage.py runserver 0.0.0.0:8000
```

Acesse `http://127.0.0.1:8000/`.

---

## Comandos de Gerenciamento Disponíveis

| Comando | Descrição |
|---------|-----------|
| `migrate` | Aplica migrações do banco de dados |
| `setup_admin` | Cria superusuário admin (`admin@semeq.com`) |
| `setup_usuarios` | Cria estrutura completa (admin, gestor, equipes PMC/SHD, líderes, colaboradores) |
| `cleanup_future_apontamentos` | Remove apontamentos com datas futuras |
| `fix_encoding` | Corrige encoding de dados importados |

---

## Estrutura de Permissões (Resumo)

| Role | Dashboard | Apontamentos | Cadastros | Usuários | Admin |
|------|-----------|--------------|-----------|----------|-------|
| **Admin** | ✅ | ✅ (todos) | ✅ | ✅ | ✅ |
| **Gestor** | ✅ | ✅ (todos) | ✅ | ✅ | ❌ |
| **Líder** | ✅ | ✅ (equipe) | ❌ | ✅ (equipe) | ❌ |
| **Colaborador** | ✅ | ✅ (próprios) | ❌ | ❌ | ❌ |

---

## Troubleshooting

### Erro de conexão com banco
- Verifique se o PostgreSQL está rodando
- Confira se `DJANGO_DB_HOST`, `DJANGO_DB_PORT`, `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD` no `.env` correspondem ao banco criado
- Teste conexão: `psql -h localhost -U admin -d apontamento`

### Migrações falham
```bash
python manage.py migrate --fake-initial
```
Ou, para resetar (CUIDADO: apaga dados):
```bash
python manage.py migrate user zero
python manage.py migrate
```

### Variáveis de ambiente não carregadas
- Certifique-se que o arquivo `.env` está na **raiz do projeto** (mesmo nível do `manage.py`)
- Reinicie o servidor após alterar o `.env`