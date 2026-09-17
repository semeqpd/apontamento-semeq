# Portal SEMEQ - Sistema de Apontamentos

Sistema web em Django para registro de apontamentos de horas e atendimentos. Permite criar, editar e acompanhar apontamentos, controlar quem os registrou, gerenciar clientes e usuários, e gerar relatórios em CSV/Excel.

## Funcionalidades

- Registro de apontamentos de horas (criação, edição, exclusão, status e exportação).
- Dashboard com indicadores e filtros por equipe, colaborador, status, prioridade e data.
- Gestão de clientes (cadastro e importação de Excel/CSV).
- Gestão de usuários com papéis e times.
- Troca rápida de status via dropdown (lista de apontamentos) com modal de confirmação para "Concluído".
- Modal de exclusão unificado (lista e detalhe) com JavaScript via event delegation.
- Permissões por role: Admin, Gestor, Líder, Colaborador.

## Requisitos

- **Python 3.12+**
- **PostgreSQL 14+** (recomendado para produção) ou SQLite (desenvolvimento rápido)
- **Git**

---

## Como rodar o projeto (Passo a passo)

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>.git
cd apontamento-semeq
# Se houver branch específica:
# git checkout teste
```

### 2. Criar e ativar ambiente virtual

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Linux/macOS / Git Bash:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente (`.env`)

Crie um arquivo **`.env` na raiz do projeto** (mesmo nível do `manage.py`):

```ini
# Django
DJANGO_SECRET_KEY=gere-uma-chave-forte-com: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Banco de dados (PostgreSQL)
DJANGO_DB_ENGINE=postgres
DJANGO_DB_NAME=apontamento
DJANGO_DB_USER=seu_usuario
DJANGO_DB_PASSWORD=sua_senha
DJANGO_DB_HOST=localhost
DJANGO_DB_PORT=5432

# Email (console para dev)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
ALLOWED_EMAIL_DOMAINS=semeq.com

# Senha do admin (obrigatório em produção)
ADMIN_PASSWORD=Semeq@123
```

> ⚠️ **Importante:** O usuário e senha do banco **devem ser exatamente iguais** aos definidos no `.env`.

### 5. Preparar o banco PostgreSQL (uma única vez)

Conecte-se como superusuário (ex: `postgres`) e execute:

```sql
-- Substitua 'seu_usuario' e 'sua_senha' pelos valores do .env
CREATE ROLE seu_usuario WITH LOGIN PASSWORD 'sua_senha' SUPERUSER CREATEDB;
CREATE DATABASE apontamento OWNER seu_usuario;
```

> **Dica:** Se preferir usar SQLite em desenvolvimento, altere no `.env`:
> ```ini
> DJANGO_DB_ENGINE=sqlite
> DJANGO_DB_NAME=db.sqlite3
> ```
> E comente/remova as variáveis `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT`.

### 6. Aplicar as migrações

```bash
python manage.py migrate
```

Todas as migrações estão incluídas (51 migrações do app `user` + apps do Django). Verifique com:

```bash
python manage.py showmigrations
# Todos devem mostrar [X]
```

### 7. Executar o setup inicial (dados obrigatórios)

```bash
python manage.py setup_admin
```

Isso cria/atualiza:
- **Superusuário admin**: `admin@semeq.com` (senha do `.env` ou fallback `Semeq@123`)
- **Equipe**: PMC
- **Cliente**: SEMEQ / LIMEIRA
- **Equipamentos**: Outro, Nenhum
- **Status fixos**: Aberto (#0d6efd), Executando (#ffc107), Concluído (#198754, is_concluido=True)
- **Cadastros auxiliares**: Tipo Problema "Teste", Atividade "Teste", Prioridade "Teste", Projeto "PMC", Solicitante "PMC"

### 8. (Opcional) Criar estrutura completa de usuários/equipes

```bash
python manage.py setup_usuarios
```

Cria 10 usuários adicionais (senha padrão `Semeq@123`):
- `gestor` (Gestor global)
- `lider_pmc`, `colab_pmc1/2/3` (Equipe PMC)
- `lider_shd`, `colab_shd1/2/3` (Equipe SHD)

> Use `--only-if-missing` para pular se já existirem:
> ```bash
> python manage.py setup_usuarios --only-if-missing
> ```

### 9. Iniciar o servidor

```bash
python manage.py runserver 0.0.0.0:8000
```

Acesse: **http://127.0.0.1:8000/**

**Login:** `admin@semeq.com` / **Senha:** `Semeq@123` (ou a definida no `ADMIN_PASSWORD`)

---

## Comandos de Gerenciamento

| Comando | Descrição |
|---------|-----------|
| `migrate` | Aplica migrações pendentes |
| `setup_admin` | Cria/atualiza admin + dados obrigatórios (equipe, cliente, status, cadastros) |
| `setup_usuarios` | Cria estrutura completa de usuários (admin, gestor, líderes, colaboradores) |
| `cleanup_future_apontamentos` | Remove apontamentos com datas futuras |
| `fix_encoding` | Corrige encoding de dados importados |

---

## Estrutura de Permissões

| Role | Dashboard | Apontamentos | Cadastros | Usuários | Admin Django |
|------|-----------|--------------|-----------|----------|--------------|
| **Admin** | ✅ | ✅ (todos) | ✅ | ✅ | ✅ |
| **Gestor** | ✅ | ✅ (todos) | ✅ | ✅ | ❌ |
| **Líder** | ✅ | ✅ (equipe) | ❌ | ✅ (equipe) | ❌ |
| **Colaborador** | ✅ | ✅ (próprios) | ❌ | ❌ | ❌ |

---

## Verificações de Integridade

### Migrações
```bash
python manage.py showmigrations
# Todos os apps devem mostrar [X] em todas as migrações
```

### Sistema
```bash
python manage.py check
# Deve retornar: "System check identified no issues (0 silenced)."
```

### Dados criados pelo setup_admin
```bash
python manage.py shell -c "
from user.models import Equipe, Cliente, Equipamento, Status, TipoProblema, Atividade, Prioridade, Projeto, Solicitante
from django.contrib.auth import get_user_model
User = get_user_model()

print('Equipes:', list(Equipe.objects.values_list('nome', flat=True)))
print('Clientes:', list(Cliente.objects.values_list('corporation', 'plant', 'zone')))
print('Equipamentos:', list(Equipamento.objects.values_list('nome', flat=True)))
print('Status:', list(Status.objects.values_list('status', 'ordem', 'cor', 'is_concluido')))
print('TipoProblema:', list(TipoProblema.objects.values_list('nome', flat=True)))
print('Atividade:', list(Atividade.objects.values_list('nome', flat=True)))
print('Prioridade:', list(Prioridade.objects.values_list('nome', flat=True)))
print('Projeto:', list(Projeto.objects.values_list('nome', flat=True)))
print('Solicitante:', list(Solicitante.objects.values_list('nome', flat=True)))
print('Usuários:', User.objects.count())
"
```

Saída esperada:
```
Equipes: ['PMC']
Clientes: [('SEMEQ', 'LIMEIRA', '')]
Equipamentos: ['Nenhum', 'Outro']
Status: [('Aberto', 1, '#0d6efd', False), ('Executando', 2, '#ffc107', False), ('Concluído', 3, '#198754', True)]
TipoProblema: ['Problema Técnico', 'Teste']
Atividade: ['Manutenção', 'Teste']
Prioridade: ['Baixa', 'Teste']
Projeto: ['PMC']
Solicitante: ['PMC']
Usuários: 1 (ou 11 se rodou setup_usuarios)
```

---

## Troubleshooting

### Erro de conexão com banco
- PostgreSQL está rodando? `systemctl status postgresql` / `services.msc`
- Verifique `.env`: `DJANGO_DB_HOST`, `DJANGO_DB_PORT`, `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`
- Teste manual: `psql -h localhost -U seu_usuario -d apontamento`
- Usuário tem permissão `SUPERUSER` ou `CREATEDB`?

### Migrações falham / banco inconsistente
```bash
# Tentar aplicar pulando inicial
python manage.py migrate --fake-initial

# Reset TOTAL (CUIDADO: APAGA DADOS)
python manage.py migrate user zero
python manage.py migrate
```

### Variáveis de ambiente não carregadas
- `.env` deve estar na **raiz** (mesmo nível do `manage.py`)
- Reinicie o terminal/servidor após alterar `.env`
- Verifique: `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DJANGO_DB_NAME'))"`

### Erro "column X does not exist" / "relation Y does not exist"
```bash
python manage.py migrate --fake-initial
# ou
python manage.py migrate user zero && python manage.py migrate
```

### Usuários duplicados / erro de integridade
O `setup_admin` e `setup_usuarios` são **idempotentes** (podem rodar múltiplas vezes). Eles limpam duplicatas automaticamente.

### Porta 8000 ocupada
```bash
python manage.py runserver 8001
# ou mate o processo: netstat -ano | findstr :8000 (Windows)
```

---

## Estrutura do Projeto (Resumo)

```
apontamento-semeq/
├── apontamento/          # Configuração do projeto (settings, urls)
├── user/                 # App principal (models, views, commands)
│   ├── management/commands/
│   │   ├── setup_admin.py      # Setup completo (RODE ESTE)
│   │   └── setup_usuarios.py   # Usuários + equipes
│   ├── models.py               # Todos os modelos
│   ├── views.py                # Views + AJAX endpoints
│   └── templates/apontamentos/
│       ├── lista.html          # Listagem com dropdown status + modal exclusão
│       ├── detail.html         # Detalhe + modal exclusão
│       └── includes/
│           ├── modal_excluir.html      # Modal unificado de exclusão
│           └── modal_tempo_conclusao.html  # Modal confirmação conclusão
├── static/
│   └── js/
├── templates/
├── requirements.txt
├── manage.py
└── .env                    # CRIE ESTE ARQUIVO
```

---

## Fluxo de Alteração de Status (Lista)

1. Usuário altera `<select class="select-status-rapido">`
2. JavaScript intercepta via `document.addEventListener('change', ...)`
3. Se status **não for "Concluído"**: POST direto para `/apontamentos/<id>/alterar-status/`
4. Se status **for "Concluído"**:
   - Abre modal `modalTempoConclusao`
   - Se `data-tempo-investido` = 0: exibe input obrigatório de minutos
   - Se > 0: apenas confirmação
5. Botão "Confirmar e Concluir" envia `status + tempo_investido_minutos` (se preenchido)
6. Backend `alterar_status_apontamento` valida, atualiza tempo e status
7. Sucesso → `location.reload()`

---

## Deploy em Produção (Checklist)

- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_SECRET_KEY` forte e único
- [ ] `DJANGO_ALLOWED_HOSTS=seu-dominio.com`
- [ ] `ADMIN_PASSWORD` forte no `.env`
- [ ] PostgreSQL com usuário/senha iguais ao `.env`
- [ ] `python manage.py collectstatic --noinput`
- [ ] Configurar Gunicorn + Nginx + systemd
- [ ] HTTPS (Let's Encrypt / certificado)
- [ ] Backup automático do banco
- [ ] Logs rotativos (`LOGGING` em settings)

---

## Licença

Proprietário - SEMEQ