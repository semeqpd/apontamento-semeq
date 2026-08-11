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

```bash
# 1. Criar e ativar o ambiente virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Configurar as variáveis de ambiente
copy .env.example .env       # Windows
# cp .env.example .env      # Linux/macOS

# 4. Aplicar as migrações
python manage.py migrate

# 5. Criar os usuários iniciais
python manage.py setup_usuarios

# 6. Rodar o servidor
python manage.py runserver 0.0.0.0:8000
```

Acesse `http://127.0.0.1:8000/`.

### Credenciais padrão

| Usuário | Senha |
|---------|-------|
| admin | Semeq@2026abc |
| gestor | Semeq@2024 |
| lider_pmc / lider_shd | Semeq@2024 |
| colab_pmc1..3 / colab_shd1..3 | Semeq@2024 |
