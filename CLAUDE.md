# CLAUDE.md

Este arquivo fornece orientações para o Claude Code (claude.ai/code) ao trabalhar com código neste repositório.

## Visão Geral do Projeto

Orfin API é uma Django REST API para gerenciamento financeiro pessoal e familiar. O sistema gerencia usuários, perfis (relatives), contas financeiras e categorias de despesas/receitas com localização brasileira (validação de CPF, idioma português).

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
# Seeding automático com dados aleatórios (via django-seed)
python manage.py seed api --number=15

# Seeding manual com dados predefinidos (recomendado para desenvolvimento)
python manage.py seed_data
```

O `seed_data` cria: 2 usuários, 3 perfis por usuário (Pessoal/Trabalho/Família), categorias com subcategorias (Moradia, Transporte, Alimentação, Saúde) e 2 contas por perfil.

## Visão Geral da Arquitetura

### Estrutura de Pastas

```
backend/
├── settings.py
├── urls.py                        # Inclui api/v1/ -> backend.api.urls
└── api/                           # App Django única (não dividida por entidade)
    ├── apps.py
    ├── admin.py                   # Registros do Django Admin
    ├── models.py                  # Re-exports centralizados dos modelos
    ├── urls.py                    # Roteamento principal da API
    ├── migrations/                # Migrações únicas (não isoladas por entidade)
    ├── core/
    │   └── handlers/
    │       └── exception_handler.py  # Handler customizado para ValidationError
    ├── utils/
    │   └── validators.py          # Validador de CPF brasileiro
    ├── management/
    │   └── commands/
    │       ├── seed_data.py       # Dados predefinidos para desenvolvimento
    │       ├── drop_db.py
    │       └── restart_db.py
    ├── tests/
    │   ├── base.py                # BaseAuthenticatedTestCase, BaseUnauthenticatedTestCase
    │   ├── constants.py           # CPFs válidos, helpers get_user_data(), get_account_data(), etc.
    │   ├── tests_user.py
    │   ├── tests_account.py
    │   ├── tests_category.py
    │   ├── tests_relative.py
    │   └── tests_validators.py
    ├── users/                     # Entidade: autenticação e perfil do usuário
    ├── relatives/                 # Entidade: perfis/parentes do usuário
    ├── accounts/                  # Entidade: contas financeiras
    └── categories/                # Entidade: categorias de despesas/receitas
```

Cada entidade contém apenas: `models.py`, `serializers.py`, `views.py`, `urls.py`. Não são apps Django completos — não possuem migrations isoladas, apps.py próprio, etc.

### Modelos Principais

**User** (`backend.api.users.models.User`)

- Estende `AbstractUser` com `UserManager` customizado
- Autenticação por email (sem username — `USERNAME_FIELD = 'email'`)
- Campos obrigatórios: `first_name`, `last_name`, `social_name`, `email`, `cpf`
- Validação de CPF brasileiro com dígitos verificadores
- Campos opcionais: `phone`
- Tabela: `auth_user_custom`
- Soft deletion via `is_active = False` (impede exclusão física)
- Métodos: `get_full_name()`, `get_display_name()`, `soft_delete()`

**Relative** (`backend.api.relatives.models.Relative`)

- Representa perfis do usuário (ex: Pessoal, Trabalho, Família)
- FK: `user` (CASCADE)
- Campos: `name`, `image_num` (nullable), `is_archived`, `created_at`, `updated_at`
- Tabela: `relative`
- Limite: máximo 3 perfis por usuário (validado em `clean()`)
- `unique_together`: (`user`, `name`)
- Soft deletion via `is_archived`
- Actions na view: `unarchive` (POST), `active` (GET)
- **Ponto de contexto**: Account e Category sempre pertencem a um Relative. O `relative_id` é passado via header `X-Relative-Id` em todas as requisições dessas entidades.

**Account** (`backend.api.accounts.models.Account`)

- Contas financeiras (bancária, dinheiro, investimentos, etc.)
- FKs: `user` (CASCADE), `relative` (CASCADE)
- Campos: `bank_name`, `name`, `description`, `account_type`, `color`, `include_calc`, `balance`, `is_archived`, `created_at`, `updated_at`
- `account_type` choices: `corrente`, `dinheiro`, `poupanca`, `investimentos`, `outros`
- `balance`: `DecimalField(max_digits=10, decimal_places=2)` — não editável via update
- `include_calc`: forçado para `False` quando `is_archived=True`
- `unique_together`: (`user`, `relative`, `name`)
- Tabela: `account`

**Category** (`backend.api.categories.models.Category`)

- Categorias de despesas/receitas com hierarquia de 1 nível
- FKs: `user` (CASCADE), `relative` (CASCADE), `subcategory` (self-referencing, nullable)
- Campos: `name`, `color` (#RRGGBB), `icon`, `is_archived`, `created_at`, `updated_at`
- `unique_together`: (`user`, `relative`, `name`, `subcategory`)
- Ao arquivar, arquiva automaticamente as subcategorias filhas
- Tabela: `category`

### Estrutura da API

- URL base: `/api/v1/`
- Autenticação JWT com SimpleJWT (Bearer token no header `Authorization`)
- Paginação: 10 itens por página (`PageNumberPagination`)
- Handler customizado converte `ValidationError` do Django em HTTP 400
- Mensagens de erro em português
- Todos os endpoints (exceto auth) exigem `IsAuthenticated`

### Mapa Completo de Endpoints

**Autenticação (`/api/v1/auth/`)**

| Método | Endpoint                 | Auth | Descrição                                    |
| ------ | ------------------------ | :--: | -------------------------------------------- |
| POST   | `/auth/register/`        |  -   | Registro de novo usuário, retorna tokens JWT |
| POST   | `/auth/login/`           |  -   | Login com email/senha, retorna tokens JWT    |
| POST   | `/auth/token/`           |  -   | Obter par de tokens JWT                      |
| POST   | `/auth/token/refresh/`   |  -   | Renovar access token                         |
| GET    | `/auth/profile/`         | sim  | Perfil completo do usuário                   |
| PUT    | `/auth/profile/`         | sim  | Atualizar perfil                             |
| GET    | `/auth/me/`              | sim  | Resumo minimalista do perfil                 |
| POST   | `/auth/change-password/` | sim  | Alterar senha                                |
| DELETE | `/auth/deactivate/`      | sim  | Desativar conta (soft delete)                |

**Perfis (`/api/v1/relatives/`)**

| Método    | Endpoint                     | Descrição                                                            |
| --------- | ---------------------------- | -------------------------------------------------------------------- |
| GET       | `/relatives/`                | Listar perfis (paginado, filtra por `is_archived`, busca por `name`) |
| POST      | `/relatives/`                | Criar perfil (máx 3 por usuário, nome único por usuário)             |
| GET       | `/relatives/{id}/`           | Detalhe do perfil                                                    |
| PUT/PATCH | `/relatives/{id}/`           | Atualizar perfil                                                     |
| DELETE    | `/relatives/{id}/`           | Arquivar perfil (soft delete)                                        |
| POST      | `/relatives/{id}/unarchive/` | Desarquivar perfil                                                   |
| GET       | `/relatives/active/`         | Listar apenas perfis ativos (sem paginação)                          |

**Contas (`/api/v1/accounts/`)** — requer header `X-Relative-Id`

| Método | Endpoint          | Descrição                                                  |
| ------ | ----------------- | ---------------------------------------------------------- |
| GET    | `/accounts/`      | Listar contas do perfil (`only_archived=true`, `name=xxx`) |
| POST   | `/accounts/`      | Criar conta                                                |
| GET    | `/accounts/{id}/` | Detalhe da conta                                           |
| PATCH  | `/accounts/{id}/` | Atualizar conta (balance não pode ser alterado via update) |
| DELETE | `/accounts/{id}/` | Arquivar conta (soft delete)                               |

**Categorias (`/api/v1/categories/`)** — requer header `X-Relative-Id`

| Método | Endpoint            | Descrição                                                      |
| ------ | ------------------- | -------------------------------------------------------------- |
| GET    | `/categories/`      | Listar categorias do perfil (`only_archived=true`, `name=xxx`) |
| POST   | `/categories/`      | Criar categoria ou subcategoria                                |
| GET    | `/categories/{id}/` | Detalhe da categoria                                           |
| PATCH  | `/categories/{id}/` | Atualizar categoria                                            |
| DELETE | `/categories/{id}/` | Arquivar categoria (e suas filhas)                             |

## Padrões e Convenções de Código

### Padrão de Soft Deletion

Todos os modelos (exceto User) usam `is_archived`. O User usa `is_active`.

```python
def delete(self, *args, **kwargs):
    # Impede exclusão física em todos os modelos
    raise NotImplementedError('Use o arquivamento.')

def soft_delete(self):
    self.is_archived = True
    self.save()
```

O ViewSet sobrescreve `destroy()` para chamar `soft_delete()` ou setar `is_archived=True` diretamente.

### Padrão Multi-Tenant por Header (X-Relative-Id)

Account e Category sempre operam no contexto de um Relative. O `relative_id` chega via header:

```python
# No serializer (create)
relative_id = self.context['request'].headers.get('X-Relative-Id')
relative = Relative.objects.get(id=relative_id, user=validated_data['user'])
validated_data['relative'] = relative

# No ViewSet (get_queryset)
relative_id = self.request.headers.get('X-Relative-Id')
queryset = queryset.filter(relative_id=relative_id)
```

### Padrão de Validação em Duas Camadas

1. **Model** (`clean()` chamado pelo `save()`): validações de integridade (limites, unicidade complexa)
2. **Serializer** (`validate_<campo>()` ou `validate()`): validações de negócio antes de chegar ao model

Validações de unicidade envolvendo `user` devem ser feitas no serializer (não depender apenas do `unique_together` do banco) para retornar mensagens amigáveis em vez de erro 500.

### Padrão de Dois Serializers por Entidade

Quando a listagem precisa de menos campos que create/update/retrieve:

```python
def get_serializer_class(self):
    if self.action == 'list':
        return RelativeListSerializer  # campos reduzidos
    return RelativeSerializer          # campos completos
```

### Padrão de Actions Customizadas no ViewSet

```python
@action(detail=True, methods=['post'])
def unarchive(self, request, pk=None):
    # Ação específica em um objeto: POST /relatives/{id}/unarchive/
    ...

@action(detail=False, methods=['get'])
def active(self, request):
    # Ação na coleção: GET /relatives/active/
    ...
```

### Padrões de Validação no Serializer

```python
def validate_name(self, value):
    # Verificar unicidade por usuário antes de chegar ao banco
    user = self.context['request'].user
    queryset = Model.objects.filter(user=user, name=value)
    if self.instance:  # Para updates: excluir o próprio registro
        queryset = queryset.exclude(pk=self.instance.pk)
    if queryset.exists():
        raise serializers.ValidationError('Mensagem amigável.')
    return value
```

### Restrições de Modelo

- Usar `unique_together` para unicidade no escopo do usuário/perfil
- Evitar exclusão física com métodos `delete()` customizados
- Sempre implementar campos de auditoria (`created_at`, `updated_at`)
- Chamar `self.clean()` dentro do `save()` para garantir validações

## Diretrizes de Testes

### Estrutura de Testes

- Testes em `backend/api/tests/`, separados por entidade
- Arquivos: `tests_user.py`, `tests_account.py`, `tests_category.py`, `tests_relative.py`, `tests_validators.py`
- Classes base em `backend/api/tests/base.py`
- Constantes e helpers em `backend/api/tests/constants.py`
- Cobertura mínima: 90% (aplicada no CI/CD)

### Classes Base de Teste

**`BaseAuthenticatedTestCase(APITestCase)`** — para testes que precisam de autenticação:

- Cria `self.user` e `self.relative` automaticamente no `setUp()`
- Autentica o cliente via JWT automaticamente
- Métodos: `authenticate_user(user)`, `create_additional_user(suffix)`, `unauthenticate()`

**`BaseUnauthenticatedTestCase(APITestCase)`** — para endpoints públicos (registro, login):

- Sem autenticação automática
- Helper: `create_user(**kwargs)`

### Helpers de Constantes

```python
from backend.api.tests.constants import (
    VALID_CPFS,           # CPFs válidos para testes
    get_user_data,        # Gera dict de dados de usuário
    get_account_data,     # Gera dict de dados de conta
    get_category_data,    # Gera dict de dados de categoria
)
```

### Estrutura de Teste de API (padrão)

```python
class RelativeAPITest(BaseAuthenticatedTestCase):
    def setUp(self):
        super().setUp()
        # Configurar header do relative para contas/categorias
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)
        self.url = reverse('nome-do-router-list')

    def test_create_success(self):
        data = {'campo': 'valor'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_duplicate_retorna_400(self):
        # Sempre testar o caminho de erro com mensagem amigável
        response = self.client.post(self.url, dados_duplicados)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Mensagem esperada', str(response.data))
```

### Executando Testes Específicos

```bash
# Arquivo completo
python manage.py test backend.api.tests.tests_relative
python manage.py test backend.api.tests.tests_account
python manage.py test backend.api.tests.tests_category
python manage.py test backend.api.tests.tests_user
python manage.py test backend.api.tests.tests_validators

# Classe específica
python manage.py test backend.api.tests.tests_relative.RelativeAPITest
python manage.py test backend.api.tests.tests_relative.RelativeModelTest

# Método específico
python manage.py test backend.api.tests.tests_relative.RelativeAPITest.test_create_relative_with_duplicate_name
```

## Notas Específicas do Projeto

### Localização Brasileira

- Idioma: Português (pt-br)
- Fuso horário: America/Sao_Paulo
- Validação de CPF com algoritmo oficial (em `backend/api/utils/validators.py`)
- Separador decimal: vírgula (,)
- Separador de milhares habilitado

### Domínio Financeiro

- Tipos de conta: `corrente`, `dinheiro`, `poupanca`, `investimentos`, `outros`
- Saldo: `DecimalField(max_digits=10, decimal_places=2)`, não editável via endpoint de update
- Cores: 6 opções predefinidas em hex para contas; formato `#RRGGBB` livre para categorias
- `include_calc`: controla se a conta entra no cálculo de saldo total (forçado `False` quando arquivada)
- Subcategorias: máximo 1 nível de profundidade

### Configurações JWT (SimpleJWT)

- Access token: 1 hora
- Refresh token: 1 dia
- `ROTATE_REFRESH_TOKENS = True` — novo refresh token a cada renovação
- `BLACKLIST_AFTER_ROTATION = True` — tokens usados são invalidados

### CI/CD

- Workflow do GitHub Actions para testes Django
- Container de serviço PostgreSQL
- Cobertura de testes deve ser ≥90%
- Executa em pull requests para branches main/develop

### Variáveis de Ambiente

Referenciar `.env.example` para variáveis obrigatórias:

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DB_HOST`, `DB_PORT`

## Depuração

```python
import pdb
pdb.set_trace()
```

Executar servidor ou testes normalmente — a execução pausará no breakpoint.

---

## Diretrizes para o Claude Code

- Sempre use nomes de variáveis, constantes, nomes de classe ou métodos descritivos e em inglês
- Sempre que editar o CLAUDE.md, mantenha suas informações em português, e mantendo em inglês apenas os nomes de variáveis, constantes, nomes de classe ou métodos.
- Sempre sugerir código com boas práticas, performance e segurança
- Os códigos gerados devem ter comentários explicando seu propósito ou relações em português, principalmente acima dos métodos.
- Se necessário uso de lib externas, durante geração de código, explique os passos necessários de instalação e uso.
- Para cada modelo que for solicitado a geração de código nesta API sugira sempre conforme padrão dos modelos já existentes: `models.py`, `serializers.py`, `views.py`, `urls.py`, arquivo de testes, atualização do `seed_data.py` e alterações ou inserções necessárias para manter tudo funcionando em outros arquivos como: `settings.py`, `admin.py`, `backend/api/urls.py`, `backend/api/models.py` e arquivos das pastas backend/api/core e backend/api/utils, etc.
- A arquitetura segue o padrão de organização por funcionalidade/domínio (users, relatives, accounts, categories) ao invés de por tipo de arquivo
- Cada entidade possui uma estrutura isolada em uma pasta contendo `models.py`, `serializers.py`, `views.py`, `urls.py`, mas não deve haver migrations isoladas. Cada entidade/pasta não é um app Django completo.
- Utilitários compartilhados ficam em `backend/api/utils/` (ex: `validators.py`)
- Handlers personalizados ficam em `backend/api/core/handlers/` (ex: `exception_handler.py`)
- O modelo `User` é o modelo de autenticação customizado do sistema e substitui o `User` padrão do Django
- Validações de unicidade por usuário devem ser feitas no serializer (`validate_<campo>`) para retornar HTTP 400 com mensagem amigável, não depender apenas do `unique_together` do banco (que gera erro 500)
- Ao criar nova entidade que use `X-Relative-Id`, seguir o padrão de `AccountSerializer` e `AccountViewSet` como referência
