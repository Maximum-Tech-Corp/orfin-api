# PRD — Orfin API

> **Documento de Requisitos de Produto — Backend**
> Versão inicial gerada em 2026-03-08. Revisar e complementar conforme o produto evolui.
>
> Para contexto de produto global, consulte o [PRD raiz do monorepo](../PRD.md).

---

## Visão do Produto

O **Orfin** é um SaaS de gerenciamento financeiro pessoal e familiar com foco no mercado brasileiro. O backend (esta API) é responsável por toda a lógica de negócio, persistência de dados, autenticação e exposição de uma API REST consumida pelo frontend.

---

## Modelo de Negócio — Planos

### Plano Pessoal

Acesso completo ao sistema de controle financeiro individual:

- Cadastro de contas financeiras
- Cadastro de despesas, receitas e transações entre contas
- Cadastro de cartões de crédito com suporte a:
  - Gastos simples
  - Gastos parcelados
- Despesas e receitas recorrentes com repetição configurável: anual, mensal, semanal ou diário, por tempo determinado ou fixo
- Tela principal de transações com seleção de mês/ano e cálculo dinâmico de saldo

### Plano Familiar

Tudo do Plano Pessoal, mais:

- Tela inicial de seleção de membro (similar à tela de perfil do Netflix)
- Dados completamente isolados por membro da família
- Limite de 3 perfis de membros individuais
- Perfil especial "Família" — somente leitura, agrega os dados de todos os membros como visão consolidada
- Sem cadastro próprio no perfil Família — apenas visualização somada

---

## Autenticação e Assinaturas

- JWT Token com expiração de 24 horas (relogin obrigatório após expirar)
- Integração com plataforma de pagamentos externa (ex: Stripe) para gestão de assinaturas
- Acesso liberado imediatamente após confirmação de pagamento
- Roadmap futuro: OAuth2 com Google e outros provedores

---

## Stack Técnica

| Componente | Tecnologia |
|---|---|
| Framework | Django + Django REST Framework |
| Banco de dados | PostgreSQL |
| Autenticação | JWT via SimpleJWT |
| Pagamentos | Stripe (planejado) |
| Localização | Português brasileiro (pt-br), fuso America/Sao_Paulo |
| Testes | Django TestCase + coverage (mínimo 90%) |
| CI/CD | GitHub Actions |
| Infraestrutura | AWS (produção) |

---

## Domínio de Dados

### Entidades Implementadas

| Entidade | Descrição | Status |
|---|---|---|
| **User** | Usuário autenticado por e-mail + CPF | ✅ Implementado |
| **Relative** | Perfil financeiro do usuário (máx. 3 pessoal / plano familiar) | ✅ Implementado |
| **Account** | Conta financeira por Perfil (corrente, poupança, dinheiro, investimentos, outros) | ✅ Implementado |
| **Category** | Categoria/subcategoria de despesa ou receita por Perfil | ✅ Implementado |

### Entidades Planejadas

| Entidade | Descrição | Status |
|---|---|---|
| **Transaction** | Lançamento financeiro (receita, despesa, transferência) | ⬜ Planejado |
| **CreditCard** | Cartão de crédito vinculado a um Perfil | ⬜ Planejado |
| **CreditCardExpense** | Gasto de fatura (simples ou parcelado) | ⬜ Planejado |
| **RecurringEntry** | Despesa/receita recorrente com configuração de frequência | ⬜ Planejado |
| **Subscription** | Controle de assinatura do usuário (plano, status, datas) | ⬜ Planejado |

### Requisitos Preliminares — Transaction

- Pertence a uma Account e Category (ambas do mesmo Relative)
- Campos essenciais: `amount`, `description`, `date`, `type` (receita/despesa/transferência), `account`, `category`
- Ao criar/editar/excluir, deve recalcular o `balance` da Account associada
- Soft deletion — sem exclusão física
- Filtros esperados: por período, por category, por type, por account

### Requisitos Preliminares — CreditCard

- Vinculado a um Relative
- Campos: `name`, `limit`, `closing_day`, `due_day`, `color`
- Gastos da fatura: simples ou parcelados (com número de parcelas e valor total)

### Requisitos Preliminares — RecurringEntry

- Despesa ou receita com repetição configurável: `daily`, `weekly`, `monthly`, `yearly`
- Pode ter data de fim ou ser indefinida
- Ao processar, gera Transactions automaticamente para o período selecionado

---

## Contratos de API

### Padrão de Resposta

- **Endpoints de auth** usam envelope: `{ "message": "...", "data": { ... } }`
- **Endpoints de recursos CRUD** usam paginação padrão DRF: `{ "count", "next", "previous", "results": [...] }`
- Mensagens de erro sempre em português

### Header Obrigatório para Recursos com Escopo de Perfil

```
X-Relative-Id: <uuid do perfil selecionado>
```

Toda requisição para `/accounts/`, `/categories/` (e futuras entidades com escopo de Relative) deve incluir este header.

### Endpoints Implementados

| Recurso | Base Path | Observação |
|---|---|---|
| Autenticação | `/api/v1/auth/` | register, login, token, refresh, profile, me, change-password, deactivate |
| Perfis | `/api/v1/relatives/` | CRUD + unarchive + active |
| Contas | `/api/v1/accounts/` | CRUD, requer `X-Relative-Id` |
| Categorias | `/api/v1/categories/` | CRUD + subcategorias, requer `X-Relative-Id` |

### Endpoints Planejados

| Recurso | Base Path | Observação |
|---|---|---|
| Transações | `/api/v1/transactions/` | requer `X-Relative-Id`; atualiza saldo da conta |
| Cartões | `/api/v1/credit-cards/` | requer `X-Relative-Id` |
| Gastos de fatura | `/api/v1/credit-cards/{id}/expenses/` | simples e parcelados |
| Recorrentes | `/api/v1/recurring/` | requer `X-Relative-Id` |
| Dashboard | `/api/v1/dashboard/` | aggregations por Relative/período |
| Assinaturas | `/api/v1/subscriptions/` | integração Stripe |

---

## Regras de Negócio Implementadas

- Usuário autenticado por e-mail (sem username)
- CPF validado com algoritmo oficial de dígitos verificadores
- Máximo 3 Perfis (Relatives) por usuário
- Nomes únicos por usuário em Relative, Account e Category (no escopo do Relative)
- Soft deletion em todos os modelos — sem exclusão física de dados financeiros
- `Account.balance` não é editável via endpoint de update — calculado pelas Transações
- `Account.include_calc` forçado para `False` quando arquivada
- Arquivar uma Category arquiva automaticamente todas as suas subcategorias filhas
- Subcategorias limitadas a 1 nível de profundidade
- Tokens JWT: access 1h, refresh 1 dia (atual); meta é access 24h para sessão diária

---

## Requisitos Não-Funcionais

- Cobertura de testes: mínimo 90% (aplicado em CI)
- Todas as mensagens de erro ao usuário em português
- Dados sensíveis (CPF, senha) nunca retornados em respostas de listagem
- Logs sem exposição de dados pessoais
- Paginação padrão de 10 itens por página
- Deploy em AWS (produção)

---

## Fora do Escopo deste Serviço

- Interface de usuário (responsabilidade do `orfin-ui`)
- Integração com Open Finance / bancos (roadmap distante)
- Envio de e-mails ou notificações push (roadmap futuro)
