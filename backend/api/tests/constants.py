"""
Constantes para testes da API.
Centraliza valores comuns como CPFs válidos, dados de usuário, etc.

Usos básicos:

# Criar usuário com dados padrão
from .constants import get_user_data
user_data = get_user_data()
user = User.objects.create_user(**user_data)

# Criar usuário adicional
user2_data = get_user_data(suffix="2", cpf_key="USER_2")
user2 = User.objects.create_user(**user2_data)

# Usar dados específicos
from .constants import BRAZILIAN_USER_DATA, REGISTRATION_USER_DATA
user = User.objects.create_user(**BRAZILIAN_USER_DATA)

# Criar conta
from .constants import get_account_data
account_data = get_account_data(name="Minha Conta Teste")
account = Account.objects.create(user=user, **account_data)

# Criar categoria
from .constants import get_category_data
category_data = get_category_data(name="Teste", color="#FF0000")
category = Category.objects.create(user=user, **category_data)
"""

# CPFs válidos para testes (com dígitos verificadores corretos)
VALID_CPFS = {
    'DEFAULT': '60017806330',     # CPF padrão para testes
    'USER_1': '60017806330',      # Mesmo que DEFAULT para compatibilidade
    'USER_2': '52998224725',      # CPF para segundo usuário
    'USER_3': '74082147831',      # CPF para terceiro usuário
    'USER_4': '11144477735',      # CPF alternativo
}

# Dados padrão para criação de usuários em testes
DEFAULT_USER_DATA = {
    'first_name': 'Test',
    'last_name': 'User',
    'social_name': 'Test User',
    'cpf': VALID_CPFS['DEFAULT'],
    'phone': '11999999999',
    'email': 'test@email.com',
    'password': 'testpass123'
}

# Dados para usuário brasileiro (usado em testes específicos)
BRAZILIAN_USER_DATA = {
    'first_name': 'João',
    'last_name': 'Silva',
    'social_name': 'João Silva',
    'cpf': VALID_CPFS['DEFAULT'],
    'phone': '11999999999',
    'email': 'joao@email.com',
    'password': 'senha123'
}

# Dados para registro via API (com confirmação de senha)
REGISTRATION_USER_DATA = {
    'first_name': 'João',
    'last_name': 'Silva',
    'social_name': 'João Silva',
    'cpf': VALID_CPFS['DEFAULT'],
    'phone': '11999999999',
    'email': 'joao@email.com',
    'password': 'senha123456',
    'password_confirm': 'senha123456'
}

# Dados padrão para contas
DEFAULT_ACCOUNT_DATA = {
    'bank_name': 'Banco do Brasil',
    'name': 'Minha Conta Corrente',
    'description': 'Conta pessoal',
    'account_type': 'corrente',
    'color': '#FF0000',
    'include_calc': True,
    'balance': '1000.00',
    'is_archived': False,
}

# Dados padrão para categorias
DEFAULT_CATEGORY_DATA = {
    'name': 'Alimentação',
    'color': '#FF5733',
    'icon': 'food',
    'is_archived': False,
    'subcategory': None
}

# Cores hexadecimais válidas para testes
VALID_HEX_COLORS = [
    '#FF5733', '#33FF57', '#3357FF',
    '#FF33F5', '#33FFF5', '#F5FF33',
    '#FF0000', '#00FF00', '#0000FF'
]

# Tipos de conta válidos
ACCOUNT_TYPES = [
    'corrente', 'dinheiro', 'poupanca',
    'investimentos', 'outros'
]

# Bancos para testes
TEST_BANKS = [
    'Nubank', 'Itaú', 'Bradesco',
    'Santander', 'Banco do Brasil', 'BTG', 'Inter'
]

# Função helper para criar dados de usuário com CPF único


def get_user_data(suffix="", cpf_key='DEFAULT', **overrides):
    """
    Retorna dados de usuário para testes com CPF válido.

    Args:
        suffix: Sufixo para email e outros campos
        cpf_key: Chave do CPF a ser usado (DEFAULT, USER_2, etc.)
        **overrides: Campos a serem sobrescritos

    Returns:
        dict: Dados do usuário
    """
    data = DEFAULT_USER_DATA.copy()

    if suffix:
        data['last_name'] = f'User{suffix}'
        data['social_name'] = f'Test User {suffix}'
        data['email'] = f'test{suffix}@email.com'
        data['phone'] = f'1199999999{suffix}'

    if cpf_key in VALID_CPFS:
        data['cpf'] = VALID_CPFS[cpf_key]

    data.update(overrides)
    return data

# Função helper para criar dados de conta


def get_account_data(**overrides):
    """
    Retorna dados de conta para testes.

    Args:
        **overrides: Campos a serem sobrescritos

    Returns:
        dict: Dados da conta
    """
    data = DEFAULT_ACCOUNT_DATA.copy()
    data.update(overrides)
    return data

# Função helper para criar dados de categoria


def get_category_data(**overrides):
    """
    Retorna dados de categoria para testes.

    Args:
        **overrides: Campos a serem sobrescritos

    Returns:
        dict: Dados da categoria
    """
    data = DEFAULT_CATEGORY_DATA.copy()
    data.update(overrides)
    return data
