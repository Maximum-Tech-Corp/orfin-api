from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from backend.api.relatives.models import Relative
from backend.api.tests.base import BaseAuthenticatedTestCase
from backend.api.tests.constants import VALID_CPFS
from backend.api.users.models import User


class RelativeModelTest(BaseAuthenticatedTestCase):
    """
    Testes para o modelo Relative.
    """

    def test_relative_creation(self):
        """
        Testa a criação de um perfil válido.
        """
        relative = Relative.objects.create(
            name='João',
            image_num=1,
            user=self.user
        )

        self.assertEqual(relative.name, 'João')
        self.assertEqual(relative.image_num, 1)
        self.assertEqual(relative.user, self.user)
        self.assertFalse(relative.is_archived)

    def test_relative_str_method(self):
        """
        Testa o método __str__ do modelo.
        """
        relative = Relative.objects.create(
            name='Maria',
            user=self.user
        )

        expected_str = f"Maria ({self.user.get_display_name()})"
        self.assertEqual(str(relative), expected_str)

    def test_relative_limit_validation(self):
        """
        Testa se a validação de limite de 3 perfis por usuário funciona.
        """
        # Já existe 1 perfil criado no setUp(), então criamos mais 2
        for i in range(2):
            Relative.objects.create(
                name=f'Perfil {i+2}',
                user=self.user
            )

        # Tenta criar o 4º perfil
        with self.assertRaises(Exception):
            Relative.objects.create(
                name='Perfil 4',
                user=self.user
            )

    def test_relative_delete_not_implemented(self):
        """
        Testa se a exclusão física é impedida.
        """
        relative = Relative.objects.create(
            name='Teste Delete',
            user=self.user
        )

        with self.assertRaises(NotImplementedError):
            relative.delete()

    def test_relative_soft_delete(self):
        """
        Testa o soft delete (arquivamento).
        """
        relative = Relative.objects.create(
            name='Teste Soft Delete',
            user=self.user
        )

        self.assertFalse(relative.is_archived)
        relative.soft_delete()
        self.assertTrue(relative.is_archived)

    def test_relative_unique_together(self):
        """
        Testa a restrição unique_together para user e name.
        """
        Relative.objects.create(
            name='Nome Único',
            user=self.user
        )

        # Tentar criar outro perfil com mesmo nome para o mesmo usuário
        with self.assertRaises(Exception):
            Relative.objects.create(
                name='Nome Único',
                user=self.user
            )

    def test_archived_relatives_count_towards_limit(self):
        """
        Testa se perfis arquivados contam para o limite de 3.
        """
        # Já existe 1 perfil criado no setUp(), criamos mais 1 e arquivamos ele
        relative_extra = Relative.objects.create(name='Perfil Extra', user=self.user)
        relative_extra.soft_delete()

        # Criamos mais 1 perfil (total: 3, sendo 1 arquivado)
        Relative.objects.create(name='Perfil 3', user=self.user)

        # Tentar criar mais um deve falhar
        with self.assertRaises(Exception):
            Relative.objects.create(name='Perfil 4', user=self.user)


class RelativeAPITest(APITestCase):
    """
    Testes para a API de Relatives.
    """

    def setUp(self):
        """
        Configuração inicial para os testes.
        """
        self.user = User.objects.create_user(
            first_name='Teste',
            last_name='User',
            social_name='Teste',
            email='teste@example.com',
            cpf=VALID_CPFS['DEFAULT'],
            password='testpass123'
        ) # type: ignore

        self.user2 = User.objects.create_user(
            first_name='Outro',
            last_name='User',
            social_name='Outro',
            email='outro@example.com',
            cpf=VALID_CPFS['USER_2'],
            password='testpass123'
        ) # type: ignore

        self.relative = Relative.objects.create(
            name='Perfil Teste',
            image_num=1,
            user=self.user
        )

        self.url = reverse('relative-list')

    def test_create_relative_authenticated(self):
        """
        Testa a criação de um perfil com usuário autenticado.
        """
        self.client.force_authenticate(user=self.user)

        data = {
            'name': 'Novo Perfil',
            'image_num': 2
        }

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Novo Perfil')
        self.assertEqual(response.data['image_num'], 2)

    def test_create_relative_unauthenticated(self):
        """
        Testa que usuários não autenticados não podem criar perfis.
        """
        data = {
            'name': 'Novo Perfil',
            'image_num': 2
        }

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_relatives_only_own(self):
        """
        Testa que usuários só veem seus próprios perfis.
        """
        # Cria perfil para outro usuário
        Relative.objects.create(
            name='Perfil Outro User',
            user=self.user2
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Perfil Teste')

    def test_update_relative(self):
        """
        Testa a atualização de um perfil.
        """
        self.client.force_authenticate(user=self.user)

        detail_url = reverse('relative-detail', kwargs={'pk': self.relative.pk})
        data = {
            'name': 'Nome Atualizado',
            'image_num': 3,
            'is_archived': True
        }

        response = self.client.put(detail_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Nome Atualizado')
        self.assertEqual(response.data['image_num'], 3)
        self.assertTrue(response.data['is_archived'])

    def test_delete_relative_archives(self):
        """
        Testa que DELETE arquiva ao invés de deletar.
        """
        self.client.force_authenticate(user=self.user)

        detail_url = reverse('relative-detail', kwargs={'pk': self.relative.pk})
        response = self.client.delete(detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verifica que o perfil foi arquivado, não deletado
        relative_updated = Relative.objects.get(pk=self.relative.pk)
        self.assertTrue(relative_updated.is_archived)

    def test_unarchive_relative(self):
        """
        Testa o endpoint para desarquivar um perfil.
        """
        self.client.force_authenticate(user=self.user)

        # Primeiro arquiva o perfil
        self.relative.soft_delete()

        unarchive_url = reverse('relative-unarchive', kwargs={'pk': self.relative.pk})
        response = self.client.post(unarchive_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_archived'])

    def test_active_relatives_endpoint(self):
        """
        Testa o endpoint que lista apenas perfis ativos.
        """
        self.client.force_authenticate(user=self.user)

        # Cria um perfil arquivado
        archived_relative = Relative.objects.create(
            name='Perfil Arquivado',
            user=self.user
        )
        archived_relative.soft_delete()

        active_url = reverse('relative-active')
        response = self.client.get(active_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Perfil Teste')

    def test_unarchive_already_active_relative(self):
        """
        Testa que tentar desarquivar um perfil já ativo retorna erro 400.
        """
        self.client.force_authenticate(user=self.user)

        # O perfil já está ativo (is_archived=False)
        unarchive_url = reverse('relative-unarchive', kwargs={'pk': self.relative.pk})
        response = self.client.post(unarchive_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Perfil já está ativo.')

    def test_create_relative_exceeds_limit(self):
        """
        Testa que não é possível criar mais de 3 perfis.
        """
        self.client.force_authenticate(user=self.user)

        # Cria mais 2 perfis (já existe 1)
        for i in range(2):
            Relative.objects.create(
                name=f'Perfil {i+2}',
                user=self.user
            )

        # Tenta criar o 4º perfil
        data = {
            'name': 'Quarto Perfil',
            'image_num': 4
        }

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_relative_with_duplicate_name(self):
        """
        Testa que criar um perfil com nome já existente retorna erro 400 amigável.
        """
        self.client.force_authenticate(user=self.user)

        # Tenta criar perfil com mesmo nome do setUp
        data = {
            'name': 'Perfil Teste',
            'image_num': 2
        }

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Você já possui um perfil com este nome.', str(response.data))

    def test_update_relative_to_duplicate_name(self):
        """
        Testa que atualizar um perfil para um nome já usado por outro perfil retorna erro 400.
        """
        self.client.force_authenticate(user=self.user)

        # Cria um segundo perfil para o mesmo usuário
        second_relative = Relative.objects.create(
            name='Segundo Perfil',
            user=self.user
        )

        # Tenta renomear o segundo perfil para o nome do primeiro
        detail_url = reverse('relative-detail', kwargs={'pk': second_relative.pk})
        data = {
            'name': 'Perfil Teste',
            'image_num': 1,
            'is_archived': False
        }

        response = self.client.put(detail_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Você já possui um perfil com este nome.', str(response.data))