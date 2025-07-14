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

    def test_delete_account(self):
        account = Account.objects.create(**self.valid_payload)
        response = self.client.delete(
            f'/api/v1/accounts/{account.id}/')  # type: ignore
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_archive_account_sets_include_calc_false(self):
        account = Account.objects.create(**self.valid_payload)
        self.assertTrue(account.include_calc)  # verify initial state

        account.is_archived = True
        account.save()

        # Refresh from database and verify include_calc was set to False
        account.refresh_from_db()
        self.assertFalse(account.include_calc)
        self.assertTrue(account.is_archived)
