from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from backend.api.users.models import User
from backend.api.relatives.models import Relative

from .constants import VALID_CPFS, get_user_data


class BaseAuthenticatedTestCase(APITestCase):
    """
    Classe base para testes que precisam de autenticação.
    Cria automaticamente um usuário e autentica o cliente.
    """

    def setUp(self):
        """
        Configuração base que cria usuário e autentica o cliente.
        """
        super().setUp()
        self.client = APIClient()

        # Cria usuário padrão para testes
        user_data = get_user_data()
        self.user = User.objects.create_user(**user_data)

        # Cria perfil padrão para o usuário
        self.relative = Relative.objects.create(
            name='Perfil Teste',
            image_num=1,
            user=self.user
        )

        # Autentica o cliente automaticamente
        self.authenticate_user(self.user)

    def authenticate_user(self, user=None):
        """
        Autentica um usuário específico ou o usuário padrão.

        Args:
            user: Usuário a ser autenticado. Se None, usa self.user
        """
        if user is None:
            user = self.user

        refresh = RefreshToken.for_user(user)
        self.client.credentials(  # type: ignore
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')  # type: ignore

    def create_additional_user(self, email_suffix="2"):
        """
        Cria um usuário adicional para testes que precisam de múltiplos usuários.

        Args:
            email_suffix: Sufixo para diferenciar o email
        """
        cpf_key = 'USER_2' if email_suffix == "2" else 'USER_3'
        user_data = get_user_data(suffix=email_suffix, cpf_key=cpf_key)
        user = User.objects.create_user(**user_data)

        # Cria perfil padrão para o usuário adicional
        Relative.objects.create(
            name='Perfil Teste',
            image_num=1,
            user=user
        )

        return user

    def unauthenticate(self):
        """
        Remove a autenticação do cliente.
        Útil para testar endpoints que devem falhar sem autenticação.
        """
        self.client.credentials()  # type: ignore


class BaseUnauthenticatedTestCase(APITestCase):
    """
    Classe base para testes que NÃO precisam de autenticação.
    Para endpoints públicos como registro e login.
    """

    def setUp(self):
        """
        Configuração base sem autenticação.
        """
        super().setUp()

    def create_user(self, **kwargs):
        """
        Helper para criar usuários nos testes.

        Args:
            **kwargs: Campos personalizados para o usuário
        """
        user_data = get_user_data(**kwargs)
        user = User.objects.create_user(**user_data)

        # Cria perfil padrão para o usuário
        Relative.objects.create(
            name='Perfil Teste',
            image_num=1,
            user=user
        )

        return user
