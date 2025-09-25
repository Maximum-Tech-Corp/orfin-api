from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from backend.api.users.models import User
from backend.api.users.serializers import (ChangePasswordSerializer,
                                           UserLoginSerializer,
                                           UserProfileSerializer,
                                           UserRegistrationSerializer)

from .constants import BRAZILIAN_USER_DATA, REGISTRATION_USER_DATA, VALID_CPFS


class UserModelTest(TestCase):
    def setUp(self):
        self.user_data = BRAZILIAN_USER_DATA.copy()
        # Remove password do dict pois será passado separadamente nos testes
        self.user_data.pop('password', None)

    def test_user_creation(self):
        user = User.objects.create_user(**self.user_data, password='senha123')
        self.assertEqual(user.email, 'joao@email.com')
        self.assertEqual(user.first_name, 'João')
        self.assertEqual(user.get_full_name(), 'João Silva')
        self.assertEqual(user.get_display_name(), 'João Silva')
        self.assertTrue(user.is_active)

    def test_cannot_user_create_without_email(self):
        user_data = self.user_data
        user_data['email'] = ''
        with self.assertRaises(ValueError) as cm:
            User.objects.create_user(**user_data, password='senha123')
        self.assertIn('O email é obrigatório', cm.exception.args)

    def test_user_string_representation(self):
        user = User.objects.create_user(**self.user_data, password='senha123')
        expected = f"{user.get_display_name()} ({user.email})"
        self.assertEqual(str(user), expected)

    def test_user_unique_email(self):
        User.objects.create_user(**self.user_data, password='senha123')

        with self.assertRaises(Exception):
            User.objects.create_user(**self.user_data, password='outrasenha')

    def test_user_unique_cpf(self):
        User.objects.create_user(**self.user_data, password='senha123')

        user_data_2 = self.user_data.copy()
        user_data_2['email'] = 'outro@email.com'
        # Mantém o mesmo CPF para testar unicidade

        with self.assertRaises(Exception):
            User.objects.create_user(**user_data_2, password='senha123')

    def test_user_soft_delete(self):
        user = User.objects.create_user(**self.user_data, password='senha123')
        self.assertTrue(user.is_active)

        user.soft_delete()
        self.assertFalse(user.is_active)

    def test_user_cannot_be_deleted(self):
        user = User.objects.create_user(**self.user_data, password='senha123')

        with self.assertRaises(NotImplementedError):
            user.delete()

    def test_create_superuser_success(self):
        """Testa criação bem sucedida de superusuário"""
        superuser = User.objects.create_superuser(
            **self.user_data, password='senha123')

        self.assertEqual(superuser.email, 'joao@email.com')
        self.assertEqual(superuser.first_name, 'João')
        self.assertTrue(superuser.is_active)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

    def test_create_superuser_without_email(self):
        """Testa falha na criação de superusuário sem email"""
        user_data = self.user_data.copy()
        user_data['email'] = ''

        with self.assertRaises(ValueError) as cm:
            User.objects.create_superuser(**user_data, password='senha123')
        self.assertIn('O email é obrigatório', cm.exception.args)

    def test_create_superuser_with_is_staff_false(self):
        """Testa falha na criação de superusuário com is_staff=False"""
        user_data = self.user_data.copy()
        user_data['is_staff'] = "False"

        with self.assertRaises(ValueError) as cm:
            User.objects.create_superuser(**user_data, password='senha123')
        self.assertIn('Superuser deve ter is_staff=True.',
                      cm.exception.args)

    def test_create_superuser_with_is_superuser_false(self):
        """Testa falha na criação de superusuário com is_superuser=False"""
        user_data = self.user_data.copy()
        user_data['is_superuser'] = "False"

        with self.assertRaises(ValueError) as cm:
            User.objects.create_superuser(**user_data, password='senha123')
        self.assertIn('Superuser deve ter is_superuser=True.',
                      cm.exception.args)

    def test_user_clean_validation_first_name_required(self):
        """Testa validação de first_name obrigatório no método clean"""
        user_data = self.user_data.copy()
        user_data['first_name'] = ''

        with self.assertRaises(ValidationError) as cm:
            User.objects.create_user(**user_data, password='senha123')
        self.assertIn('O primeiro nome é obrigatório', str(cm.exception))

    def test_user_clean_validation_last_name_required(self):
        """Testa validação de last_name obrigatório no método clean"""
        user_data = self.user_data.copy()
        user_data['last_name'] = ''

        with self.assertRaises(ValidationError) as cm:
            User.objects.create_user(**user_data, password='senha123')
        self.assertIn('O sobrenome é obrigatório', str(cm.exception))

    def test_user_clean_validation_social_name_required(self):
        """Testa validação de social_name obrigatório no método clean"""
        user_data = self.user_data.copy()
        user_data['social_name'] = ''

        with self.assertRaises(ValidationError) as cm:
            User.objects.create_user(**user_data, password='senha123')
        self.assertIn('O nome social é obrigatório', str(cm.exception))

    def test_user_clean_validation_cpf_required(self):
        """Testa validação de CPF obrigatório no método clean"""
        user_data = self.user_data.copy()
        user_data['cpf'] = ''

        with self.assertRaises(ValidationError) as cm:
            User.objects.create_user(**user_data, password='senha123')
        self.assertIn('O CPF é obrigatório', str(cm.exception))

    def test_user_clean_validation_email_required(self):
        """Testa validação de email obrigatório no método clean"""
        user_data = self.user_data.copy()
        user_data['email'] = ''

        # Como o email é validado tanto no manager quanto no clean,
        # testamos a validação do clean criando um usuário diretamente
        user = User(**user_data)
        with self.assertRaises(ValidationError) as cm:
            user.clean()
        self.assertIn('O email é obrigatório', str(cm.exception))


class UserAuthenticationAPITest(APITestCase):
    def setUp(self):
        self.register_url = reverse('user-register')
        self.login_url = reverse('user-login')
        self.profile_url = reverse('user-profile')
        self.change_password_url = reverse('change-password')
        self.deactivate_url = reverse('deactivate-user')
        self.me_url = reverse('user-profile-summary')

        self.valid_user_data = REGISTRATION_USER_DATA.copy()

    def test_user_registration_success(self):
        response = self.client.post(self.register_url, self.valid_user_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.json())
        self.assertIn('access', response.json().get('data'))
        self.assertIn('refresh', response.json().get('data'))
        self.assertIn('user', response.json().get('data'))

    def test_user_registration_password_mismatch(self):
        invalid_data = self.valid_user_data.copy()
        invalid_data['password_confirm'] = 'senhadiferente'

        response = self.client.post(self.register_url, invalid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_registration_duplicate_email(self):
        # Criar usuário primeiro
        User.objects.create_user(**BRAZILIAN_USER_DATA)

        response = self.client.post(self.register_url, self.valid_user_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_login_success(self):
        # Criar usuário primeiro
        user = User.objects.create_user(**BRAZILIAN_USER_DATA)

        login_data = {
            'email': 'joao@email.com',
            'password': 'senha123'
        }

        response = self.client.post(self.login_url, login_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.json())
        self.assertIn('access', response.json().get('data'))

    def test_user_login_invalid_credentials(self):
        login_data = {
            'email': 'inexistente@email.com',
            'password': 'senhaerrada'
        }

        response = self.client.post(self.login_url, login_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_profile_authenticated(self):
        user = User.objects.create_user(**BRAZILIAN_USER_DATA)

        # Autenticar usuário
        refresh = RefreshToken.for_user(user)
        self.client.credentials(  # type: ignore
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')  # type: ignore

        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get('email'), 'joao@email.com')

    def test_user_profile_unauthenticated(self):
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_success(self):
        user = User.objects.create_user(**BRAZILIAN_USER_DATA)

        # Autenticar usuário
        refresh = RefreshToken.for_user(user)
        self.client.credentials(  # type: ignore
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')  # type: ignore

        change_data = {
            'current_password': 'senha123',
            'new_password': 'novasenha123',
            'new_password_confirm': 'novasenha123'
        }

        response = self.client.post(self.change_password_url, change_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_current(self):
        user = User.objects.create_user(**BRAZILIAN_USER_DATA)

        # Autenticar usuário
        refresh = RefreshToken.for_user(user)
        self.client.credentials(  # type: ignore
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')  # type: ignore

        change_data = {
            'current_password': 'senhaerrada',
            'new_password': 'novasenha123',
            'new_password_confirm': 'novasenha123'
        }

        response = self.client.post(self.change_password_url, change_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_deactivation(self):
        user = User.objects.create_user(**BRAZILIAN_USER_DATA)

        # Autenticar usuário
        refresh = RefreshToken.for_user(user)
        self.client.credentials(  # type: ignore
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')  # type: ignore

        response = self.client.delete(self.deactivate_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verificar se usuário foi desativado
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_user_profile_summary(self):
        user = User.objects.create_user(**BRAZILIAN_USER_DATA)

        # Autenticar usuário
        refresh = RefreshToken.for_user(user)
        self.client.credentials(  # type: ignore
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')  # type: ignore

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.json())
        self.assertEqual(response.json().get(
            'data').get('email'), 'joao@email.com')
        self.assertEqual(response.json().get(
            'data').get('display_name'), 'João Silva')


class UserSerializerTest(TestCase):
    """
    Testes para os serializers do usuário.
    """

    def setUp(self):
        self.user_data = BRAZILIAN_USER_DATA.copy()
        self.registration_data = REGISTRATION_USER_DATA.copy()
        # Criar usuário para testes de duplicata
        self.existing_user = User.objects.create_user(**self.user_data)

    def test_registration_duplicate_cpf_validation(self):
        """
        Testa validação de CPF duplicado
        Testa diretamente o método validate_cpf do serializer
        """
        serializer = UserRegistrationSerializer()

        # Simular CPF já existente no banco
        with self.assertRaises(Exception) as cm:
            serializer.validate_cpf(self.existing_user.cpf)  # type: ignore
        self.assertIn('Este CPF já está registrado', str(cm.exception))

    def test_registration_duplicate_email_validation(self):
        """
        Testa validação de email duplicado
        Testa diretamente o método validate_email do serializer
        """
        serializer = UserRegistrationSerializer()

        # Simular email já existente no banco (testando normalização também)
        with self.assertRaises(Exception) as cm:
            serializer.validate_email(  # type: ignore
                self.existing_user.email.upper())
        self.assertIn('Este email já está registrado', str(cm.exception))

    def test_login_inactive_user_validation(self):
        """
        Testa validação de usuário inativo
        Criar um mock direto para testar apenas a validação de usuário inativo
        """
        from unittest.mock import Mock, patch

        from backend.api.users.serializers import UserLoginSerializer

        serializer = UserLoginSerializer()

        # Mock de usuário inativo
        mock_inactive_user = Mock()
        mock_inactive_user.is_active = False

        # Patch do authenticate para retornar o usuário mockado
        with patch('backend.api.users.serializers.authenticate', return_value=mock_inactive_user):
            with self.assertRaises(Exception) as cm:
                serializer.validate({
                    'email': 'test@test.com',
                    'password': 'senha123'
                })
            self.assertIn('Conta de usuário desativada', str(cm.exception))

    def test_login_missing_fields_validation(self):
        """
        Testa validação de campos obrigatórios
        Teste com apenas o email omitido (password presente mas vazio)
        """
        serializer_data = {'password': ''}
        serializer = UserLoginSerializer(data=serializer_data)
        self.assertFalse(serializer.is_valid())
        # Campo obrigatório vai gerar erro de campo primeiro
        self.assertIn('email', serializer.errors)

        # Teste com valores None
        serializer_data = {'email': '', 'password': ''}
        serializer = UserLoginSerializer(data=serializer_data)
        # Força a passagem pelos campos obrigatórios
        if serializer.is_valid():
            # Se passou na validação de campo, testa o validate()
            pass
        else:
            # Deve falhar na validação de campo obrigatório
            self.assertTrue(
                'email' in serializer.errors or 'password' in serializer.errors)

    def test_login_missing_fields_direct_validate(self):
        """Testa diretamente o método validate"""
        serializer = UserLoginSerializer()

        # Teste com campos vazios
        with self.assertRaises(Exception) as cm:
            serializer.validate({'email': '', 'password': ''})
        self.assertIn('Deve incluir "email" e "password"', str(cm.exception))

        # Teste com email None
        with self.assertRaises(Exception) as cm:
            serializer.validate({'email': None, 'password': 'senha123'})
        self.assertIn('Deve incluir "email" e "password"', str(cm.exception))

        # Teste com password None
        with self.assertRaises(Exception) as cm:
            serializer.validate({'email': 'test@email.com', 'password': None})
        self.assertIn('Deve incluir "email" e "password"', str(cm.exception))

    def test_profile_cpf_change_validation(self):
        """
        Testa validação de alteração de CPF
        O CPF está como read_only_field no Meta, então não será validado
        Vamos testar diretamente o método validate_cpf
        """
        serializer = UserProfileSerializer(instance=self.existing_user)

        # Testar alteração de CPF no método validate_cpf diretamente
        with self.assertRaises(Exception) as cm:
            serializer.validate_cpf('98765432100')  # type: ignore
        self.assertIn('O CPF não pode ser alterado', str(cm.exception))

        # Testar normalização do CPF (deve passar sem erro)
        serializer.validate_cpf(self.existing_user.cpf)  # type: ignore

    def test_profile_email_change_validation(self):
        """
        Testa validação de alteração de email
        O email está como read_only_field no Meta, então não será validado
        Vamos testar diretamente o método validate_email
        """
        serializer = UserProfileSerializer(instance=self.existing_user)

        # Testar alteração de email no método validate_email diretamente
        with self.assertRaises(Exception) as cm:
            serializer.validate_email('newemail@email.com')  # type: ignore
        self.assertIn('O email não pode ser alterado', str(cm.exception))
        # Testar normalização do email (deve passar sem erro)
        serializer.validate_email(self.existing_user.email)  # type: ignore

    def test_change_password_mismatch_validation(self):
        """Testa validação de senhas não coincidentes"""
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post('/change-password/')
        request.user = self.existing_user

        serializer_data = {
            'current_password': 'senha123',
            'new_password': 'novasenha123',
            'new_password_confirm': 'senhadiferente123'
        }

        serializer = ChangePasswordSerializer(
            data=serializer_data,
            context={'request': request}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('new_password_confirm', serializer.errors)
        self.assertEqual(
            serializer.errors['new_password_confirm'][0], 'As senhas não coincidem.')  # type: ignore


class UserViewsAdditionalTest(APITestCase):
    """
    Testes adicionais para atingir 100% de cobertura das views
    """

    def setUp(self):
        self.user_data = BRAZILIAN_USER_DATA.copy()
        self.user = User.objects.create_user(**self.user_data)

        # URLs necessárias
        self.profile_url = reverse('user-profile')
        self.token_obtain_url = reverse('token-obtain-pair')
        self.token_refresh_url = reverse('token-refresh')

    def test_user_profile_patch_update(self):
        """Testa atualização parcial do perfil (PATCH)"""
        # Autenticar usuário
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(  # type: ignore
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')  # type: ignore

        # Dados parciais para atualização
        patch_data = {
            'first_name': 'João Atualizado'
        }

        response = self.client.patch(self.profile_url, patch_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.json())
        self.assertEqual(response.json().get('message'),
                         'Perfil atualizado com sucesso.')
        self.assertIn('data', response.json())

        # Verificar se apenas o campo first_name foi atualizado
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'João Atualizado')

    def test_custom_token_obtain_pair_view(self):
        """Testa CustomTokenObtainPairView"""
        login_data = {
            'email': 'joao@email.com',
            'password': 'senha123'
        }

        response = self.client.post(self.token_obtain_url, login_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.json())
        self.assertEqual(response.json().get('message'),
                         'Tokens gerados com sucesso.')
        self.assertIn('data', response.json())
        self.assertIn('access', response.json().get('data'))
        self.assertIn('refresh', response.json().get('data'))
        self.assertIn('user', response.json().get('data'))

    def test_custom_token_refresh_view_success(self):
        """Testa CustomTokenRefreshView com sucesso"""
        # Obter token de refresh válido
        refresh = RefreshToken.for_user(self.user)

        refresh_data = {
            'refresh': str(refresh)
        }

        response = self.client.post(self.token_refresh_url, refresh_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.json())
        self.assertEqual(response.json().get('message'),
                         'Token renovado com sucesso.')
        self.assertIn('data', response.json())
        self.assertIn('access', response.json().get('data'))

    def test_custom_token_refresh_view_invalid_token(self):
        """Testa CustomTokenRefreshView com token inválido"""
        refresh_data = {
            'refresh': 'token_invalido'
        }

        response = self.client.post(self.token_refresh_url, refresh_data)

        # Deve retornar erro sem modificação da resposta personalizada
        # Quando status_code != 200, retorna response original da classe pai
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        # Verificar que não tem a estrutura personalizada de resposta
        self.assertNotIn('message', response.json())
