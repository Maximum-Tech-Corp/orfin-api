from rest_framework import status

from backend.api.accounts.models import Account

from .base import BaseAuthenticatedTestCase
from .constants import get_account_data


class AccountTestCase(BaseAuthenticatedTestCase):
    def setUp(self):
        super().setUp()  # Chama o setUp da classe base (autentica automaticamente)
        self.valid_payload = get_account_data()
        # Configura header padrão para todos os testes
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)

    def test_create_account(self):
        response = self.client.post(
            '/api/v1/accounts/', self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(str(Account.objects.first()),
                         "Minha Conta Corrente - Banco do Brasil")

    def test_create_account_with_name_already_exits(self):
        self.client.post(
            '/api/v1/accounts/', self.valid_payload, format='json')
        response = self.client.post(
            '/api/v1/accounts/', self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_account_invalid_include_calc(self):
        payload = self.valid_payload.copy()
        payload.update({'is_archived': True, 'include_calc': True})
        response = self.client.post(
            '/api/v1/accounts/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()[
                         'non_field_errors'][0], 'Não é permitido manter include_calc true e manter is_archived false.')

    def test_list_accounts_default_active(self):
        Account.objects.create(user=self.user, relative=self.relative, **self.valid_payload)

        # Cria conta arquivada
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Account.objects.create(user=self.user, relative=self.relative, **archived_payload)

        response = self.client.get('/api/v1/accounts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 1 conta ativa
        self.assertEqual(len(response.json().get('results')), 1)

    def test_list_accounts_only_archived(self):
        # Cria conta ativa
        Account.objects.create(user=self.user, relative=self.relative, **self.valid_payload)

        # Cria conta arquivada
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Account.objects.create(user=self.user, relative=self.relative, **archived_payload)

        response = self.client.get('/api/v1/accounts/?only_archived=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 1 conta arquivada
        self.assertEqual(len(response.json().get('results')), 1)

    def test_list_accounts_only_by_name(self):
        # Cria conta ativa
        Account.objects.create(user=self.user, relative=self.relative, **self.valid_payload)

        # Cria outra conta
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Meus investimentos',
        })
        Account.objects.create(user=self.user, relative=self.relative, **archived_payload)

        response = self.client.get('/api/v1/accounts/?name=Corrente')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 1 conta, a ativa
        self.assertEqual(len(response.json().get('results')), 1)

    def test_update_account(self):
        account = Account.objects.create(user=self.user, relative=self.relative, **self.valid_payload)
        update_payload = {'name': 'Conta Atualizada'}
        response = self.client.patch(
            f'/api/v1/accounts/{account.id}/', update_payload, format='json')  # type: ignore
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['name'], 'Conta Atualizada')

    def test_update_account_balance(self):
        account = Account.objects.create(user=self.user, relative=self.relative, **self.valid_payload)
        update_payload = {'balance': 500}
        response = self.client.patch(
            f'/api/v1/accounts/{account.id}/', update_payload, format='json')  # type: ignore
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('balance', response.json())

    def test_delete_nonexistent_account(self):
        response = self.client.delete('/api/v1/accounts/999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_account_archives_instead(self):
        account = Account.objects.create(user=self.user, relative=self.relative, **self.valid_payload)

        response = self.client.delete(f'/api/v1/accounts/{account.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('arquivada', response.json().get('detail'))

        # Verifica se a conta foi arquivada
        account.refresh_from_db()
        self.assertTrue(account.is_archived)

    def test_archive_account_sets_include_calc_false(self):
        account = Account.objects.create(user=self.user, relative=self.relative, **self.valid_payload)
        self.assertTrue(account.include_calc)  # verify initial state

        account.is_archived = True
        account.save()

        # Refresh from database and verify include_calc was set to False
        account.refresh_from_db()
        self.assertFalse(account.include_calc)
        self.assertTrue(account.is_archived)

    def test_user_can_only_see_own_accounts(self):
        # Cria conta para o usuário atual
        Account.objects.create(user=self.user, relative=self.relative, **self.valid_payload)

        # Cria outro usuário e uma conta para ele
        other_user = self.create_additional_user()
        other_relative = other_user.relatives.first()
        other_payload = self.valid_payload.copy()
        other_payload['name'] = 'Conta do Outro Usuário'
        Account.objects.create(user=other_user, relative=other_relative, **other_payload)

        # Faz requisição como usuário atual
        response = self.client.get('/api/v1/accounts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 1 conta (a do usuário atual)
        self.assertEqual(len(response.json().get('results')), 1)
        self.assertEqual(response.json().get('results')[
                         0]['name'], 'Minha Conta Corrente')

    def test_user_cannot_access_other_user_account(self):
        # Cria outro usuário e uma conta para ele
        other_user = self.create_additional_user()
        other_relative = other_user.relatives.first()
        other_payload = self.valid_payload.copy()
        other_payload['name'] = 'Conta do Outro Usuário'
        other_account = Account.objects.create(
            user=other_user, relative=other_relative, **other_payload)

        # Tenta acessar conta do outro usuário
        response = self.client.get(f'/api/v1/accounts/{other_account.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_access_accounts(self):
        # Remove autenticação
        self.unauthenticate()

        response = self.client.get('/api/v1/accounts/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_accounts_with_invalid_relative_id(self):
        # Envia um relative_id que não existe para o listing
        self.client.defaults['HTTP_X_RELATIVE_ID'] = '99999'

        response = self.client.get('/api/v1/accounts/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('X-Relative-Id', response.json())

    def test_create_account_without_relative_header(self):
        # Remove o header X-Relative-Id para garantir que a validação é acionada
        self.client.defaults.pop('HTTP_X_RELATIVE_ID', None)

        response = self.client.post(
            '/api/v1/accounts/', self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Header X-Relative-Id é obrigatório.', str(response.json()))

    def test_create_account_with_invalid_relative_id(self):
        # Envia um relative_id que não existe no banco
        self.client.defaults['HTTP_X_RELATIVE_ID'] = '99999'

        response = self.client.post(
            '/api/v1/accounts/', self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Perfil não encontrado ou não pertence ao usuário.', str(response.json()))
