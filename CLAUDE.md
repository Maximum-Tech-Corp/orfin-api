# CLAUDE.md

Este arquivo fornece orientações para o Claude Code (claude.ai/code) ao trabalhar com código neste repositório.

## Visão Geral do Projeto

Orfin API é uma Django REST API para gerenciamento financeiro pessoal e familiar. Este é o componente de API backend. O sistema gerencia usuários, contas financeiras e categorias de despesas com localização brasileira (validação de CPF, idioma português).

## Configuração de Desenvolvimento

### Configuração do Ambiente

```bash
# Clonar e configurar
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Configuração do ambiente
python contrib/env_gen.py
# Editar arquivo .env com suas credenciais de banco de dados

# Configuração do banco de dados
python manage.py migrate
python manage.py createsuperuser --username="admin" --email=""
```

### Requisitos do Banco de Dados

- Banco de dados PostgreSQL
- Configurar conexão no arquivo .env usando as variáveis do .env.example

## Comandos Comuns de Desenvolvimento

### Executando a Aplicação

```bash
python manage.py runserver
```

### Comandos de Testes

```bash
# Executar todos os testes
python manage.py test

# Executar testes com cobertura (mínimo de 90% obrigatório)
coverage run manage.py test
coverage report -m

# Atualizar badge de cobertura do README
python contrib/update_coverage.py
```

### Gerenciamento do Banco de Dados

```bash
# Remover e recriar todas as tabelas do banco de dados
python manage.py restart_db

# Remover apenas todas as tabelas do banco de dados
python manage.py drop_db

# Aplicar migrações
python manage.py migrate
python manage.py makemigrations
```

### Seeding de Dados

```bash
# Seeding automático com dados aleatórios
python manage.py seed api --number=15

# Seeding manual com dados predefinidos
python manage.py seed_data
```

## Visão Geral da Arquitetura

### Modelos Principais

**User Model** (`backend.api.users.models.User`)

- Estende o AbstractUser do Django com UserManager customizado
- Autenticação baseada em email (sem username)
- Validação de CPF brasileiro com dígitos verificadores
- Campos obrigatórios: first_name, last_name, social_name, email, cpf
- Campos opcionais: phone
- Tabela personalizada: `auth_user_custom`
- Soft deletion implementada (impedindo exclusão física)
- Métodos auxiliares: get_full_name(), get_display_name(), soft_delete()

**Account Model** (`backend.api.accounts.models.Account`)

- Contas financeiras do usuário (contas bancárias, dinheiro, investimentos)
- Soft deletion (arquivamento) - exclusão física é impedida
- Rastreamento de saldo com precisão decimal
- Codificação por cores e categorização
- Restrição única: usuário + nome da conta

**Category Model** (`backend.api.categories.models.Category`)

- Categorias de despesas/receitas do usuário
- Estrutura hierárquica (máximo de um nível de subcategorias)
- Soft deletion (arquivamento) - exclusão física é impedida
- Suporte a cores e ícones
- Restrição única: nome + subcategoria dentro do escopo do usuário

### Estrutura da API

- URL base: `/api/v1/`
- Endpoints RESTful para usuários, contas e categorias
- Sistema de autenticação JWT com refresh tokens
- Manipulador de exceção personalizado para Django ValidationError em `backend.api.core.handlers`
- Paginação habilitada (10 itens por página)
- Mensagens de erro em português e localização

### Sistema de Autenticação e Usuários

**Endpoints de Autenticação (`/api/v1/auth/`):**

- `POST /register/` - Registro de novo usuário
- `POST /login/` - Login do usuário
- `POST /token/` - Obter token JWT
- `POST /token/refresh/` - Refresh do token JWT

**Endpoints de Perfil:**

- `GET/PUT /profile/` - Gerenciamento completo do perfil
- `GET /me/` - Resumo do perfil do usuário
- `POST /change-password/` - Alteração de senha
- `POST /deactivate/` - Desativação da conta

## Padrões e Convenções de Código

### Padrão de Soft Deletion

- Sobrescrever método `delete()` para lançar NotImplementedError
- Usar campo `is_archived` para soft deletion
- Manipular arquivamento na camada de view (tipicamente nos métodos destroy)

### Padrões de Validação

- Métodos `clean()` personalizados para validações complexas
- Chamar `clean()` no método `save()`
- Validação de CPF usando algoritmo brasileiro em `api.utils.validators`

### Restrições de Modelo

- Usar `unique_together` para unicidade no escopo do usuário
- Evitar exclusão física com métodos delete personalizados
- Implementar campos de auditoria (`created_at`, `updated_at`)

## Diretrizes de Testes

### Estrutura de Testes

- Testes localizados em `backend/api/tests/`
- Arquivos de teste separados por funcionalidade: `tests_user.py`, `tests_account.py`, `tests_category.py`, `tests_validators.py`
- Classe base `BaseTestCase` em `backend/api/tests/base.py` com utilitários comuns
- Constantes de teste centralizadas em `backend/api/tests/constants.py`
- Requisito de 90% de cobertura de testes aplicado no CI/CD

### Executando Testes Específicos

```bash
# Executar arquivo de teste específico
python manage.py test backend.api.tests.tests_user
python manage.py test backend.api.tests.tests_account
python manage.py test backend.api.tests.tests_category
python manage.py test backend.api.tests.tests_validators

# Executar classe de teste específica
python manage.py test backend.api.tests.tests_user.UserModelTest
python manage.py test backend.api.tests.tests_account.AccountModelTest

# Executar método de teste específico
python manage.py test backend.api.tests.tests_user.UserModelTest.test_user_creation
python manage.py test backend.api.tests.tests_account.AccountModelTest.test_account_creation
```

## Notas Específicas do Projeto

### Localização Brasileira

- Idioma: Português (pt-br)
- Fuso horário: America/Sao_Paulo
- Validação de CPF com algoritmo oficial
- Separador decimal: vírgula (,)
- Separador de milhares habilitado

### Domínio Financeiro

- Tipos de conta: corrente, dinheiro, poupanca, investimentos, outros
- Saldo armazenado como DecimalField (max_digits=10, decimal_places=2)
- Codificação por cores para organização visual
- Incluir/excluir contas dos cálculos via campo `include_calc`

### CI/CD

- Workflow do GitHub Actions para testes Django
- Container de serviço PostgreSQL
- Cobertura de testes deve ser ≥90%
- Executa em pull requests para branches main/develop

### Variáveis de Ambiente

Referenciar `.env.example` para variáveis de ambiente obrigatórias:

- Configuração do banco de dados (PostgreSQL)
- Django SECRET_KEY
- Configuração DEBUG
- ALLOWED_HOSTS

## Depuração

Usar breakpoints do debugger Python no código:

```python
import pdb
pdb.set_trace()
```

Então executar servidor ou testes normalmente - a execução pausará no breakpoint.

- Sempre use nomes de variáveis, constantes, nomes de classe ou métodos descritivos e em inglês
- Sempre que editar o CLAUDE.md, mantenha suas informações em português, e mantendo em inglês apenas os nomes de variáveis, constantes, nomes de classe ou métodos.
- Sempre sugerir código com boas práticas, performance e segurança
- Os códigos gerados devem ter comentários explicando seu propósito ou relações em português, principalmente acima dos métodos.
- Se necessário uso de lib externas, durante geração de código, explique os passos necessários de instalação e uso.
- Para cada modelo que solicitar geração de código nesta API sugira sempre todos os arquivos básicos (criação ou edição): models, serializers, views, urls, arquivos de testes, alteração/atualização no arquivo de seed (backend/api/management/commands/seed_data.py) e outras alterações ou criações necessárias para o pleno funcionamento do conjunto (exemplo: settings.py, arquivos na pasta utils, core, etc)
- A arquitetura segue o padrão de organização por funcionalidade/domínio (users, accounts, categories) ao invés de por tipo de arquivo
- Cada entidade possui uma estrutura isolada em uma pasta contendo models.py, serializers.py, views.py, urls.py, mas não deve haver migrations isoladas. Em outras palavras cada entidade/pasta continua sendo uma entidade (que pode se integrar com as outras como chave estrangeira por exemplo), mas não são um app Django completo.
- Utilitários compartilhados ficam em backend/api/utils/ (ex: validators.py)
- Handlers personalizados ficam em backend/api/core/handlers/ (ex: exception_handler.py)
- O modelo User é o modelo de autenticação customizado do sistema e substitui o User padrão do Django
