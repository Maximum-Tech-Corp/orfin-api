from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from backend.api.accounts.models import Account


class AccountTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.valid_payload = {
            'bank_name': 'Banco do Brasil',
            'name': 'Minha Conta Corrente',
            'description': 'Conta pessoal',
            'account_type': 'corrente',
            'color': '#FF0000',
            'include_calc': True,
            'balance': '1000.00',
            'is_archived': False,
        }

    def test_create_account(self):
        response = self.client.post(
            '/api/v1/accounts/', self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Account.objects.count(), 1)

    def test_create_account_invalid_include_calc(self):
        payload = self.valid_payload.copy()
        payload.update({'is_archived': True, 'include_calc': True})
        response = self.client.post(
            '/api/v1/accounts/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()[
                         'non_field_errors'][0], 'Não é permitido manter include_calc true e manter is_archived false.')

    def test_list_accounts_default_active(self):
        """
        Testa listagem de contas padrão.
        """
        # Cria conta ativa
        Account.objects.create(**self.valid_payload)

        # Cria conta arquivada
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Account.objects.create(**archived_payload)

        response = self.client.get('/api/v1/accounts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 1 conta ativa
        self.assertEqual(len(response.json().get('results')), 1)

    def test_list_accounts_only_archived(self):
        """
        Testa listagem de contas arquivadas.
        """
        # Cria conta ativa
        Account.objects.create(**self.valid_payload)

        # Cria conta arquivada
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Account.objects.create(**archived_payload)

        response = self.client.get('/api/v1/accounts/?only_archived=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 1 conta arquivada
        self.assertEqual(len(response.json().get('results')), 1)

    def test_list_accounts_only_by_name(self):
        """
        Testa listagem de contas por nome
        """
        # Cria conta ativa
        Account.objects.create(**self.valid_payload)

        # Cria outra conta
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Meus investimentos',
        })
        Account.objects.create(**archived_payload)

        response = self.client.get('/api/v1/accounts/?name=Corrente')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 1 conta, a ativa
        self.assertEqual(len(response.json().get('results')), 1)

    def test_update_account(self):
        account = Account.objects.create(**self.valid_payload)
        update_payload = {'name': 'Conta Atualizada'}
        response = self.client.patch(
            f'/api/v1/accounts/{account.id}/', update_payload, format='json')  # type: ignore
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['name'], 'Conta Atualizada')

    def test_update_account_balance(self):
        account = Account.objects.create(**self.valid_payload)
        update_payload = {'balance': 500}
        response = self.client.patch(
            f'/api/v1/accounts/{account.id}/', update_payload, format='json')  # type: ignore
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('balance', response.json())

    def test_delete_nonexistent_account(self):
        """
        Testa delete de conta inexistente.
        """
        response = self.client.delete('/api/v1/accounts/999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_account_archives_instead(self):
        """
        Testa a action delete definir is_archived na conta ao invés de deleta-la.
        """
        account = Account.objects.create(**self.valid_payload)

        response = self.client.delete(f'/api/v1/accounts/{account.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('arquivada', response.json().get('detail'))

        # Verifica se a conta foi arquivada
        account.refresh_from_db()
        self.assertTrue(account.is_archived)

    def test_archive_account_sets_include_calc_false(self):
        account = Account.objects.create(**self.valid_payload)
        self.assertTrue(account.include_calc)  # verify initial state

        account.is_archived = True
        account.save()

        # Refresh from database and verify include_calc was set to False
        account.refresh_from_db()
        self.assertFalse(account.include_calc)
        self.assertTrue(account.is_archived)
