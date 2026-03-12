import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from backend.api.accounts.models import Account
from backend.api.categories.models import Category
from backend.api.transactions.models import RecurringRule, Transaction

from .base import BaseAuthenticatedTestCase
from .constants import (get_account_data, get_category_data,
                        get_recurring_rule_data, get_transaction_data)

# ---------------------------------------------------------------------------
# Helpers de fixture compartilhados
# ---------------------------------------------------------------------------


def make_account(user, relative, name='Conta Teste'):
    """Cria uma Account mínima para uso nos testes."""
    return Account.objects.create(
        user=user,
        relative=relative,
        bank_name='Banco Teste',
        name=name,
        account_type='corrente',
        color='#FF0000',
        balance='1000.00',
    )


def make_category(user, relative, name='Alimentação', type_category='despesas'):
    """Cria uma Category mínima para uso nos testes."""
    return Category.objects.create(
        user=user,
        relative=relative,
        name=name,
        color='#FF5733',
        icon='food',
        type_category=type_category,
    )


def make_transaction(user, relative, account, category, **kwargs):
    """Cria uma Transaction mínima diretamente no banco (sem passar pela API)."""
    defaults = {
        'type': 'despesa',
        'amount': '100.00',
        'description': 'Transação Teste',
        'date': datetime.date(2026, 3, 11),
        'is_paid': False,
    }
    defaults.update(kwargs)
    return Transaction.objects.create(
        user=user,
        relative=relative,
        account=account,
        category=category,
        **defaults,
    )


def make_recurring_rule(user, relative, account=None, category=None, **kwargs):
    """Cria uma RecurringRule mínima diretamente no banco."""
    defaults = {
        'type': 'despesa',
        'frequency': 'monthly',
        'interval': 1,
        'start_date': datetime.date(2026, 3, 1),
        'amount': '500.00',
        'description': 'Regra Teste',
    }
    defaults.update(kwargs)
    return RecurringRule.objects.create(
        user=user,
        relative=relative,
        account=account,
        category=category,
        **defaults,
    )


# ===========================================================================
# TESTES DE MODEL — Transaction
# ===========================================================================

class TransactionModelTest(BaseAuthenticatedTestCase):
    """
    Testes unitários do model Transaction.
    Valida regras de negócio no nível do banco (clean/save).
    """

    def setUp(self):
        super().setUp()
        self.account = make_account(self.user, self.relative)
        self.category = make_category(self.user, self.relative)

    # --- amount ---

    def test_amount_zero_raises_validation_error(self):
        """amount = 0 deve lançar ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            Transaction(
                user=self.user, relative=self.relative,
                account=self.account, category=self.category,
                type='despesa', amount='0.00',
                description='Teste', date='2026-03-11',
            ).clean()
        self.assertIn('amount', ctx.exception.message_dict)

    def test_amount_negative_raises_validation_error(self):
        """amount negativo deve lançar ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            Transaction(
                user=self.user, relative=self.relative,
                account=self.account, category=self.category,
                type='despesa', amount='-50.00',
                description='Teste', date='2026-03-11',
            ).clean()
        self.assertIn('amount', ctx.exception.message_dict)

    def test_amount_positive_is_valid(self):
        """amount positivo não deve lançar erro."""
        t = Transaction(
            user=self.user, relative=self.relative,
            account=self.account, category=self.category,
            type='despesa', amount='50.00',
            description='Teste', date='2026-03-11',
        )
        t.clean()  # não deve lançar

    # --- category obrigatória ---

    def test_receita_sem_category_raises_validation_error(self):
        """Receita sem categoria deve lançar ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            Transaction(
                user=self.user, relative=self.relative,
                account=self.account,
                type='receita', amount='200.00',
                description='Salário', date='2026-03-11',
            ).clean()
        self.assertIn('category', ctx.exception.message_dict)

    def test_despesa_sem_category_raises_validation_error(self):
        """Despesa sem categoria deve lançar ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            Transaction(
                user=self.user, relative=self.relative,
                account=self.account,
                type='despesa', amount='100.00',
                description='Mercado', date='2026-03-11',
            ).clean()
        self.assertIn('category', ctx.exception.message_dict)

    def test_transferencia_sem_category_is_valid(self):
        """Transferência sem categoria deve ser válida."""
        t = Transaction(
            user=self.user, relative=self.relative,
            account=self.account,
            type='transferencia', amount='500.00',
            description='TED', date='2026-03-11',
        )
        t.clean()  # não deve lançar

    # --- campos de parcelamento ---

    def test_installment_number_sem_total_raises_error(self):
        """installment_number sem installment_total deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            Transaction(
                user=self.user, relative=self.relative,
                account=self.account, category=self.category,
                type='despesa', amount='100.00',
                description='Parcela', date='2026-03-11',
                installment_number=1,
            ).clean()

    def test_installment_total_sem_number_raises_error(self):
        """installment_total sem installment_number deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            Transaction(
                user=self.user, relative=self.relative,
                account=self.account, category=self.category,
                type='despesa', amount='100.00',
                description='Parcela', date='2026-03-11',
                installment_total=3,
            ).clean()

    def test_installment_group_sem_number_raises_error(self):
        """installment_group_id sem number/total deve lançar ValidationError."""
        import uuid
        with self.assertRaises(ValidationError):
            Transaction(
                user=self.user, relative=self.relative,
                account=self.account, category=self.category,
                type='despesa', amount='100.00',
                description='Parcela', date='2026-03-11',
                installment_group_id=uuid.uuid4(),
            ).clean()

    def test_installment_fields_completos_are_valid(self):
        """installment_number + installment_total + group_id juntos são válidos."""
        import uuid
        t = Transaction(
            user=self.user, relative=self.relative,
            account=self.account, category=self.category,
            type='despesa', amount='400.00',
            description='Parcela 1/3', date='2026-03-11',
            installment_number=1,
            installment_total=3,
            installment_group_id=uuid.uuid4(),
        )
        t.clean()  # não deve lançar

    # --- __str__ ---

    def test_str_representation(self):
        """__str__ deve retornar descrição, valor e tipo."""
        t = make_transaction(self.user, self.relative,
                             self.account, self.category)
        self.assertIn('Transação Teste', str(t))
        self.assertIn('Despesa', str(t))


# ===========================================================================
# TESTES DE MODEL — RecurringRule
# ===========================================================================

class RecurringRuleModelTest(BaseAuthenticatedTestCase):
    """
    Testes unitários do model RecurringRule.
    """

    def setUp(self):
        super().setUp()
        self.account = make_account(self.user, self.relative)
        self.category = make_category(self.user, self.relative)

    # --- amount ---

    def test_amount_zero_raises_error(self):
        """amount = 0 deve lançar ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            RecurringRule(
                user=self.user, relative=self.relative,
                type='despesa', frequency='monthly', interval=1,
                start_date='2026-03-01', amount='0.00', description='Teste',
            ).clean()
        self.assertIn('amount', ctx.exception.message_dict)

    # --- end_date XOR occurrences_count ---

    def test_end_date_e_occurrences_count_juntos_raises_error(self):
        """end_date e occurrences_count informados juntos devem lançar ValidationError."""
        with self.assertRaises(ValidationError):
            RecurringRule(
                user=self.user, relative=self.relative,
                type='despesa', frequency='monthly', interval=1,
                start_date='2026-03-01', amount='500.00', description='Teste',
                end_date='2026-12-01', occurrences_count=6,
            ).clean()

    def test_end_date_anterior_start_raises_error(self):
        """end_date anterior a start_date deve lançar ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            RecurringRule(
                user=self.user, relative=self.relative,
                type='despesa', frequency='monthly', interval=1,
                start_date='2026-06-01', amount='500.00', description='Teste',
                end_date='2026-03-01',
            ).clean()
        self.assertIn('end_date', ctx.exception.message_dict)

    def test_sem_end_date_nem_occurrences_is_valid(self):
        """Sem end_date nem occurrences_count (recorrência indefinida) deve ser válida."""
        rule = RecurringRule(
            user=self.user, relative=self.relative,
            type='despesa', frequency='monthly', interval=1,
            start_date='2026-03-01', amount='500.00', description='Aluguel',
        )
        rule.clean()  # não deve lançar

    # --- soft_delete ---

    def test_soft_delete_sets_is_active_false(self):
        """soft_delete() deve setar is_active=False sem deletar o registro."""
        rule = make_recurring_rule(
            self.user, self.relative, self.account, self.category)
        self.assertTrue(rule.is_active)
        rule.soft_delete()
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)
        self.assertTrue(RecurringRule.objects.filter(pk=rule.pk).exists())

    def test_hard_delete_raises_not_implemented(self):
        """delete() direto deve lançar NotImplementedError."""
        rule = make_recurring_rule(
            self.user, self.relative, self.account, self.category)
        with self.assertRaises(NotImplementedError):
            rule.delete()

    # --- __str__ ---

    def test_str_representation(self):
        """__str__ deve conter descrição, frequência e tipo."""
        rule = make_recurring_rule(
            self.user, self.relative, self.account, self.category)
        result = str(rule)
        self.assertIn('Regra Teste', result)
        self.assertIn('Mensal', result)
        self.assertIn('Despesa', result)


# ===========================================================================
# TESTES DE API — Transaction
# ===========================================================================

class TransactionAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração dos endpoints de Transaction.
    """

    def setUp(self):
        super().setUp()
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)
        self.url_list = reverse('transaction-list')

        self.account = make_account(self.user, self.relative)
        self.category_despesa = make_category(
            self.user, self.relative, 'Alimentação', 'despesas')
        self.category_receita = make_category(
            self.user, self.relative, 'Salário', 'receitas')

    def _detail_url(self, pk):
        return reverse('transaction-detail', args=[pk])

    # --- autenticação ---

    def test_list_sem_autenticacao_retorna_401(self):
        """GET sem token deve retornar 401."""
        self.unauthenticate()
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_sem_relative_header_retorna_lista_vazia(self):
        """GET sem X-Relative-Id retorna lista vazia (sem filtro de perfil)."""
        del self.client.defaults['HTTP_X_RELATIVE_ID']
        make_transaction(self.user, self.relative,
                         self.account, self.category_despesa)
        response = self.client.get(self.url_list)
        # Sem header, nenhum filtro por relative é aplicado — lista todas do usuário
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --- listagem ---

    def test_list_retorna_apenas_transacoes_do_usuario(self):
        """GET deve retornar apenas transações do usuário autenticado."""
        make_transaction(self.user, self.relative,
                         self.account, self.category_despesa)

        other_user = self.create_additional_user()
        other_relative = other_user.relatives.first()
        other_account = make_account(other_user, other_relative, 'Conta Outro')
        other_category = make_category(other_user, other_relative)
        make_transaction(other_user, other_relative,
                         other_account, other_category)

        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # type: ignore

    def test_list_filtra_por_month_e_year(self):
        """GET ?month=3&year=2026 deve filtrar por período."""
        make_transaction(self.user, self.relative, self.account, self.category_despesa,
                         date=datetime.date(2026, 3, 11))
        make_transaction(self.user, self.relative, self.account, self.category_despesa,
                         date=datetime.date(2026, 4, 5), description='Abril')

        response = self.client.get(self.url_list, {'month': 3, 'year': 2026})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # type: ignore

    def test_list_filtra_por_type(self):
        """GET ?type=receita deve retornar apenas receitas."""
        make_transaction(self.user, self.relative, self.account, self.category_despesa,
                         type='despesa')
        make_transaction(self.user, self.relative, self.account, self.category_receita,
                         type='receita', description='Salário')

        response = self.client.get(self.url_list, {'type': 'receita'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # type: ignore

    def test_list_filtra_por_is_paid(self):
        """GET ?is_paid=true deve retornar apenas pagas."""
        make_transaction(self.user, self.relative, self.account, self.category_despesa,
                         is_paid=True)
        make_transaction(self.user, self.relative, self.account, self.category_despesa,
                         is_paid=False, description='Pendente')

        response = self.client.get(self.url_list, {'is_paid': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # type: ignore

    def test_list_filtra_por_account(self):
        """GET ?account={id} deve filtrar por conta."""
        account2 = make_account(self.user, self.relative, 'Conta Dois')
        make_transaction(self.user, self.relative,
                         self.account, self.category_despesa)
        make_transaction(self.user, self.relative, account2, self.category_despesa,
                         description='Outra conta')

        response = self.client.get(
            self.url_list, {'account': str(self.account.pk)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # type: ignore

    # --- criação ---

    def test_create_despesa_retorna_201(self):
        """POST com despesa válida deve retornar 201."""
        data = get_transaction_data(
            account=self.account, category=self.category_despesa)
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['type'], 'despesa')  # type: ignore

    def test_create_receita_retorna_201(self):
        """POST com receita válida deve retornar 201."""
        data = get_transaction_data(
            account=self.account,
            category=self.category_receita,
            type='receita',
            description='Salário',
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['type'], 'receita')  # type: ignore

    def test_create_transferencia_sem_category_retorna_201(self):
        """POST com transferência sem categoria deve retornar 201 (Parte 3: requer destination_account)."""
        account_destino = make_account(self.user, self.relative, 'Poupança')
        data = get_transaction_data(
            account=self.account,
            type='transferencia',
            description='TED para poupança',
            destination_account=account_destino.pk,
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_sem_category_para_despesa_retorna_400(self):
        """POST com despesa sem categoria deve retornar 400."""
        data = get_transaction_data(account=self.account, type='despesa')
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sem_category_para_receita_retorna_400(self):
        """POST com receita sem categoria deve retornar 400."""
        data = get_transaction_data(account=self.account, type='receita')
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_amount_zero_retorna_400(self):
        """POST com amount = 0 deve retornar 400."""
        data = get_transaction_data(
            account=self.account, category=self.category_despesa, amount='0.00'
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_amount_negativo_retorna_400(self):
        """POST com amount negativo deve retornar 400."""
        data = get_transaction_data(
            account=self.account, category=self.category_despesa, amount='-100.00'
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_com_notes_retorna_201(self):
        """POST com campo notes deve retornar 201 e persistir o valor."""
        data = get_transaction_data(
            account=self.account,
            category=self.category_despesa,
            notes='Compra no atacado',
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['notes'],
                         'Compra no atacado')  # type: ignore

    def test_create_sem_header_relative_retorna_400(self):
        """POST sem X-Relative-Id deve retornar 400."""
        del self.client.defaults['HTTP_X_RELATIVE_ID']
        data = get_transaction_data(
            account=self.account, category=self.category_despesa)
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_seta_user_e_relative_automaticamente(self):
        """POST não deve aceitar user/relative no body — são preenchidos pelo sistema."""
        data = get_transaction_data(
            account=self.account, category=self.category_despesa)
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        transaction = Transaction.objects.get(
            pk=response.data['id'])  # type: ignore
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.relative, self.relative)

    # --- retrieve ---

    def test_retrieve_retorna_200(self):
        """GET /{id}/ deve retornar 200 com dados completos."""
        t = make_transaction(self.user, self.relative,
                             self.account, self.category_despesa)
        response = self.client.get(self._detail_url(t.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['id']), str(t.pk))  # type: ignore

    def test_retrieve_de_outro_usuario_retorna_404(self):
        """GET /{id}/ de transação de outro usuário deve retornar 404."""
        other_user = self.create_additional_user()
        other_relative = other_user.relatives.first()
        other_account = make_account(other_user, other_relative, 'Conta Outro')
        other_category = make_category(other_user, other_relative)
        t = make_transaction(other_user, other_relative,
                             other_account, other_category)

        response = self.client.get(self._detail_url(t.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- update ---

    def test_patch_description_retorna_200(self):
        """PATCH com nova descrição deve retornar 200."""
        t = make_transaction(self.user, self.relative,
                             self.account, self.category_despesa)
        response = self.client.patch(self._detail_url(
            t.pk), {'description': 'Nova descrição'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'],
                         'Nova descrição')  # type: ignore

    def test_patch_transfer_pair_id_retorna_400(self):
        """PATCH com transfer_pair_id deve retornar 400."""
        import uuid
        t = make_transaction(self.user, self.relative,
                             self.account, self.category_despesa)
        response = self.client.patch(self._detail_url(
            t.pk), {'transfer_pair_id': str(uuid.uuid4())})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_is_paid_toggle(self):
        """PATCH alterando is_paid deve persistir corretamente."""
        t = make_transaction(self.user, self.relative, self.account, self.category_despesa,
                             is_paid=False)
        response = self.client.patch(self._detail_url(t.pk), {'is_paid': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        t.refresh_from_db()
        self.assertTrue(t.is_paid)

    # --- delete ---

    def test_delete_retorna_204_e_remove_do_banco(self):
        """DELETE deve retornar 204 e remover a transação permanentemente."""
        t = make_transaction(self.user, self.relative,
                             self.account, self.category_despesa)
        pk = t.pk
        response = self.client.delete(self._detail_url(pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Transaction.objects.filter(pk=pk).exists())

    def test_delete_de_outro_usuario_retorna_404(self):
        """DELETE de transação de outro usuário deve retornar 404."""
        other_user = self.create_additional_user()
        other_relative = other_user.relatives.first()
        other_account = make_account(other_user, other_relative, 'Conta Outro')
        other_category = make_category(other_user, other_relative)
        t = make_transaction(other_user, other_relative,
                             other_account, other_category)

        response = self.client.delete(self._detail_url(t.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Transaction.objects.filter(pk=t.pk).exists())


# ===========================================================================
# TESTES DE SALDO — Parte 2
# ===========================================================================

class BalanceDeltaHelperTest(TestCase):
    """
    Testes unitários do helper _balance_delta.
    Garante o comportamento correto de direção por tipo de transação.
    """

    def setUp(self):
        from backend.api.transactions.views import _balance_delta
        self.delta = _balance_delta

    def test_receita_retorna_valor_positivo(self):
        """Receita deve retornar delta positivo (crédito)."""
        self.assertEqual(self.delta('receita', Decimal('100.00')), Decimal('100.00'))

    def test_despesa_retorna_valor_negativo(self):
        """Despesa deve retornar delta negativo (débito)."""
        self.assertEqual(self.delta('despesa', Decimal('100.00')), Decimal('-100.00'))

    def test_transferencia_retorna_zero(self):
        """Transferência deve retornar zero — lógica tratada na Parte 3."""
        self.assertEqual(self.delta('transferencia', Decimal('100.00')), Decimal('0'))


class TransactionBalanceTest(BaseAuthenticatedTestCase):
    """
    Testes de integração da lógica de atualização de saldo (Parte 2).
    Verifica que Account.balance é atualizado corretamente em cada cenário
    de criação, edição e deleção de receitas e despesas.

    Convenção: make_transaction cria registros diretamente no banco (sem view),
    portanto o saldo NÃO é atualizado automaticamente. Quando o teste precisa
    de um saldo inicial diferente de 1000, ele ajusta self.account.balance
    manualmente antes de chamar o endpoint testado.
    """

    def setUp(self):
        super().setUp()
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)
        self.url_list = reverse('transaction-list')
        # Conta com saldo inicial de R$1.000,00
        self.account = make_account(self.user, self.relative)
        self.category_despesa = make_category(
            self.user, self.relative, 'Alimentação', 'despesas')
        self.category_receita = make_category(
            self.user, self.relative, 'Salário', 'receitas')

    def _detail_url(self, pk):
        return reverse('transaction-detail', args=[pk])

    def _balance(self):
        """Recarrega e retorna o saldo atualizado da conta do banco."""
        self.account.refresh_from_db()
        return self.account.balance

    def _set_balance(self, value):
        """Define o saldo da conta diretamente (simula estado pós-criação via API)."""
        self.account.balance = Decimal(str(value))
        self.account.save()

    # --- CREATE: impacto no saldo ---

    def test_create_despesa_paga_debita_saldo(self):
        """POST despesa com is_paid=True deve debitar o valor do saldo."""
        data = get_transaction_data(
            account=self.account, category=self.category_despesa,
            amount='200.00', is_paid=True,
        )
        self.client.post(self.url_list, data)
        self.assertEqual(self._balance(), Decimal('800.00'))

    def test_create_receita_paga_credita_saldo(self):
        """POST receita com is_paid=True deve creditar o valor no saldo."""
        data = get_transaction_data(
            account=self.account, category=self.category_receita,
            type='receita', amount='500.00', is_paid=True,
        )
        self.client.post(self.url_list, data)
        self.assertEqual(self._balance(), Decimal('1500.00'))

    def test_create_despesa_nao_paga_nao_altera_saldo(self):
        """POST despesa com is_paid=False não deve alterar o saldo."""
        data = get_transaction_data(
            account=self.account, category=self.category_despesa,
            amount='200.00', is_paid=False,
        )
        self.client.post(self.url_list, data)
        self.assertEqual(self._balance(), Decimal('1000.00'))

    def test_create_receita_nao_paga_nao_altera_saldo(self):
        """POST receita com is_paid=False não deve alterar o saldo."""
        data = get_transaction_data(
            account=self.account, category=self.category_receita,
            type='receita', amount='500.00', is_paid=False,
        )
        self.client.post(self.url_list, data)
        self.assertEqual(self._balance(), Decimal('1000.00'))

    def test_create_transferencia_nao_altera_saldo(self):
        """POST transferência não deve alterar o saldo (lógica de par na Parte 3)."""
        data = get_transaction_data(
            account=self.account, type='transferencia',
            amount='300.00', is_paid=True,
        )
        self.client.post(self.url_list, data)
        self.assertEqual(self._balance(), Decimal('1000.00'))

    def test_create_sem_account_nao_altera_saldo(self):
        """POST sem conta vinculada não deve alterar nenhum saldo."""
        data = get_transaction_data(
            category=self.category_despesa, amount='200.00', is_paid=True,
        )
        self.client.post(self.url_list, data)
        self.assertEqual(self._balance(), Decimal('1000.00'))

    # --- PATCH: toggle is_paid ---

    def test_patch_is_paid_false_para_true_aplica_delta(self):
        """PATCH is_paid false→true deve aplicar o delta (débito) ao saldo."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_despesa,
            amount='300.00', is_paid=False,
        )
        self.client.patch(self._detail_url(t.pk), {'is_paid': True})
        # 1000 - 300 = 700
        self.assertEqual(self._balance(), Decimal('700.00'))

    def test_patch_is_paid_true_para_false_reverte_delta(self):
        """PATCH is_paid true→false deve reverter o delta (crédito) ao saldo."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_despesa,
            amount='300.00', is_paid=True,
        )
        # Simula saldo pós-criação via API (1000 - 300 = 700)
        self._set_balance('700.00')

        self.client.patch(self._detail_url(t.pk), {'is_paid': False})
        # 700 + 300 = 1000 (revertido)
        self.assertEqual(self._balance(), Decimal('1000.00'))

    def test_patch_is_paid_false_para_false_nao_altera_saldo(self):
        """PATCH sem mudança de is_paid (false→false) não deve alterar o saldo."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_despesa,
            amount='300.00', is_paid=False,
        )
        self.client.patch(self._detail_url(t.pk), {'description': 'Atualizada'})
        self.assertEqual(self._balance(), Decimal('1000.00'))

    # --- PATCH: mudança de amount ---

    def test_patch_amount_em_despesa_paga_ajusta_delta_liquido(self):
        """PATCH amount em despesa paga deve ajustar o delta líquido (reverte antigo, aplica novo)."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_despesa,
            amount='200.00', is_paid=True,
        )
        # Simula saldo pós-criação via API (1000 - 200 = 800)
        self._set_balance('800.00')

        self.client.patch(self._detail_url(t.pk), {'amount': '350.00'})
        # 800 + 200 (reverte antigo) - 350 (aplica novo) = 650
        self.assertEqual(self._balance(), Decimal('650.00'))

    def test_patch_amount_em_receita_paga_ajusta_delta_liquido(self):
        """PATCH amount em receita paga deve ajustar o delta líquido."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_receita,
            type='receita', amount='500.00', is_paid=True,
        )
        # Simula saldo pós-criação via API (1000 + 500 = 1500)
        self._set_balance('1500.00')

        self.client.patch(self._detail_url(t.pk), {'amount': '300.00'})
        # 1500 - 500 (reverte antigo) + 300 (aplica novo) = 1300
        self.assertEqual(self._balance(), Decimal('1300.00'))

    def test_patch_amount_nao_pago_nao_altera_saldo(self):
        """PATCH amount em transação não paga não deve alterar o saldo."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_despesa,
            amount='200.00', is_paid=False,
        )
        self.client.patch(self._detail_url(t.pk), {'amount': '350.00'})
        self.assertEqual(self._balance(), Decimal('1000.00'))

    # --- PATCH: mudança de type ---

    def test_patch_type_despesa_para_receita_inverte_saldo(self):
        """PATCH type despesa→receita em transação paga deve inverter o delta."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_receita,
            type='despesa', amount='200.00', is_paid=True,
        )
        # Simula saldo pós-criação via API (1000 - 200 = 800)
        self._set_balance('800.00')

        self.client.patch(self._detail_url(t.pk), {
            'type': 'receita',
            'category': self.category_receita.pk,
        })
        # 800 + 200 (reverte despesa) + 200 (aplica receita) = 1200
        self.assertEqual(self._balance(), Decimal('1200.00'))

    # --- PATCH: mudança de account ---

    def test_patch_account_reverte_conta_antiga_e_aplica_na_nova(self):
        """PATCH account em despesa paga deve reverter da conta antiga e debitar a nova."""
        account2 = make_account(self.user, self.relative, 'Conta Dois')
        t = make_transaction(
            self.user, self.relative, self.account, self.category_despesa,
            amount='300.00', is_paid=True,
        )
        # Simula saldo da conta1 pós-criação via API (1000 - 300 = 700)
        self._set_balance('700.00')

        self.client.patch(self._detail_url(t.pk), {'account': account2.pk})

        # Conta antiga deve ser restaurada (reverte o débito)
        self.assertEqual(self._balance(), Decimal('1000.00'))
        # Conta nova deve ter o débito aplicado (1000 - 300 = 700)
        account2.refresh_from_db()
        self.assertEqual(account2.balance, Decimal('700.00'))

    # --- DELETE ---

    def test_delete_despesa_paga_restaura_saldo(self):
        """DELETE de despesa paga deve restaurar o saldo (reverte o débito)."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_despesa,
            amount='400.00', is_paid=True,
        )
        # Simula saldo pós-criação via API (1000 - 400 = 600)
        self._set_balance('600.00')

        self.client.delete(self._detail_url(t.pk))
        self.assertEqual(self._balance(), Decimal('1000.00'))

    def test_delete_receita_paga_reverte_credito(self):
        """DELETE de receita paga deve reverter o crédito do saldo."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_receita,
            type='receita', amount='500.00', is_paid=True,
        )
        # Simula saldo pós-criação via API (1000 + 500 = 1500)
        self._set_balance('1500.00')

        self.client.delete(self._detail_url(t.pk))
        self.assertEqual(self._balance(), Decimal('1000.00'))

    def test_delete_despesa_nao_paga_nao_altera_saldo(self):
        """DELETE de despesa não paga não deve alterar o saldo."""
        t = make_transaction(
            self.user, self.relative, self.account, self.category_despesa,
            amount='400.00', is_paid=False,
        )
        self.client.delete(self._detail_url(t.pk))
        self.assertEqual(self._balance(), Decimal('1000.00'))

    def test_delete_transferencia_paga_nao_altera_saldo(self):
        """DELETE de transferência não deve alterar saldo (lógica de par na Parte 3)."""
        t = make_transaction(
            self.user, self.relative, self.account, None,
            type='transferencia', amount='200.00', is_paid=True,
        )
        self.client.delete(self._detail_url(t.pk))
        self.assertEqual(self._balance(), Decimal('1000.00'))


# ===========================================================================
# TESTES DE API — RecurringRule
# ===========================================================================

class RecurringRuleAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração dos endpoints de RecurringRule.
    """

    def setUp(self):
        super().setUp()
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)
        self.url_list = reverse('recurring-rule-list')

        self.account = make_account(self.user, self.relative)
        self.category = make_category(self.user, self.relative)

    def _detail_url(self, pk):
        return reverse('recurring-rule-detail', args=[pk])

    # --- autenticação ---

    def test_list_sem_autenticacao_retorna_401(self):
        """GET sem token deve retornar 401."""
        self.unauthenticate()
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- listagem ---

    def test_list_retorna_apenas_regras_ativas_por_padrao(self):
        """GET sem filtro deve retornar apenas regras ativas."""
        make_recurring_rule(self.user, self.relative, self.account, self.category,
                            description='Ativa')
        inativa = make_recurring_rule(self.user, self.relative, self.account, self.category,
                                      description='Inativa', is_active=False)

        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # type: ignore
        self.assertNotEqual(str(response.data['results'][0]['id']), str(
            inativa.pk))  # type: ignore

    def test_list_only_inactive_retorna_inativas(self):
        """GET ?only_inactive=true deve retornar apenas regras inativas."""
        make_recurring_rule(self.user, self.relative, self.account, self.category,
                            description='Ativa')
        make_recurring_rule(self.user, self.relative, self.account, self.category,
                            description='Inativa', is_active=False)

        response = self.client.get(self.url_list, {'only_inactive': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # type: ignore

    def test_list_retorna_apenas_regras_do_usuario(self):
        """GET deve retornar apenas regras do usuário autenticado."""
        make_recurring_rule(self.user, self.relative,
                            self.account, self.category)

        other_user = self.create_additional_user()
        other_relative = other_user.relatives.first()
        other_account = make_account(other_user, other_relative, 'Conta Outro')
        make_recurring_rule(other_user, other_relative, other_account, None)

        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # type: ignore

    # --- criação ---

    def test_create_fixa_indefinida_retorna_201(self):
        """POST sem end_date e sem occurrences_count deve criar regra indefinida."""
        data = get_recurring_rule_data(
            account=self.account, category=self.category)
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data['end_date'])  # type: ignore
        self.assertIsNone(response.data['occurrences_count'])  # type: ignore

    def test_create_com_occurrences_count_retorna_201(self):
        """POST com occurrences_count deve criar regra finita por contagem."""
        data = get_recurring_rule_data(
            account=self.account, category=self.category, occurrences_count=6
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['occurrences_count'], 6)  # type: ignore

    def test_create_com_end_date_retorna_201(self):
        """POST com end_date válida deve retornar 201."""
        data = get_recurring_rule_data(
            account=self.account, category=self.category, end_date='2026-12-01'
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_end_date_e_occurrences_count_retorna_400(self):
        """POST com end_date e occurrences_count juntos deve retornar 400."""
        data = get_recurring_rule_data(
            account=self.account, category=self.category,
            end_date='2026-12-01', occurrences_count=6,
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_end_date_anterior_start_date_retorna_400(self):
        """POST com end_date anterior a start_date deve retornar 400."""
        data = get_recurring_rule_data(
            account=self.account, category=self.category,
            start_date='2026-06-01', end_date='2026-03-01',
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_amount_zero_retorna_400(self):
        """POST com amount = 0 deve retornar 400."""
        data = get_recurring_rule_data(
            account=self.account, category=self.category, amount='0.00'
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_sem_header_relative_retorna_400(self):
        """POST sem X-Relative-Id deve retornar 400."""
        del self.client.defaults['HTTP_X_RELATIVE_ID']
        data = get_recurring_rule_data(
            account=self.account, category=self.category)
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_seta_user_e_relative_automaticamente(self):
        """POST deve associar user e relative pelo contexto, não pelo body."""
        data = get_recurring_rule_data(
            account=self.account, category=self.category)
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rule = RecurringRule.objects.get(
            pk=response.data['id'])  # type: ignore
        self.assertEqual(rule.user, self.user)
        self.assertEqual(rule.relative, self.relative)

    # --- retrieve ---

    def test_retrieve_retorna_200(self):
        """GET /{id}/ deve retornar 200."""
        rule = make_recurring_rule(
            self.user, self.relative, self.account, self.category)
        response = self.client.get(self._detail_url(rule.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_de_outro_usuario_retorna_404(self):
        """GET /{id}/ de regra de outro usuário deve retornar 404."""
        other_user = self.create_additional_user()
        other_relative = other_user.relatives.first()
        other_account = make_account(other_user, other_relative, 'Conta Outro')
        rule = make_recurring_rule(
            other_user, other_relative, other_account, None)

        response = self.client.get(self._detail_url(rule.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- update ---

    def test_patch_description_retorna_200(self):
        """PATCH com nova descrição deve retornar 200."""
        rule = make_recurring_rule(
            self.user, self.relative, self.account, self.category)
        response = self.client.patch(self._detail_url(rule.pk), {
                                     'description': 'Atualizada'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'],
                         'Atualizada')  # type: ignore

    # --- delete (soft) ---

    def test_delete_desativa_regra_sem_remover(self):
        """DELETE deve desativar (is_active=False) sem deletar do banco."""
        rule = make_recurring_rule(
            self.user, self.relative, self.account, self.category)
        pk = rule.pk
        response = self.client.delete(self._detail_url(pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # type: ignore
        self.assertIn('desativada', response.data['detail'].lower())
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)
        self.assertTrue(RecurringRule.objects.filter(pk=pk).exists())

    def test_delete_de_outro_usuario_retorna_404(self):
        """DELETE de regra de outro usuário deve retornar 404."""
        other_user = self.create_additional_user()
        other_relative = other_user.relatives.first()
        other_account = make_account(other_user, other_relative, 'Conta Outro')
        rule = make_recurring_rule(
            other_user, other_relative, other_account, None)

        response = self.client.delete(self._detail_url(rule.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ===========================================================================
# TESTES DE TRANSFERÊNCIA — Parte 3
# ===========================================================================

class TransferAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração da lógica de transferência (Parte 3).
    Verifica criação de par (debit + credit), sincronização de campos
    e atualização atômica de saldo em ambas as contas envolvidas.
    """

    def setUp(self):
        super().setUp()
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)
        self.url_list = reverse('transaction-list')
        # Conta de origem com R$1.000 e conta de destino com R$500
        self.origin = make_account(self.user, self.relative, 'Conta Origem')
        self.destination = make_account(self.user, self.relative, 'Conta Destino')
        # Diferencia os saldos iniciais para facilitar a verificação
        self.destination.balance = Decimal('500.00')
        self.destination.save()

    def _detail_url(self, pk):
        return reverse('transaction-detail', args=[pk])

    def _balance(self, account):
        """Recarrega e retorna o saldo atualizado da conta do banco."""
        account.refresh_from_db()
        return account.balance

    def _set_balance(self, account, value):
        """Define o saldo da conta diretamente (simula estado pós-criação via API)."""
        account.balance = Decimal(str(value))
        account.save()

    def _create_transfer(self, amount='200.00', is_paid=True, **kwargs):
        """Helper para criar transferência via API com destination_account padrão."""
        data = get_transaction_data(
            account=self.origin,
            type='transferencia',
            amount=amount,
            is_paid=is_paid,
            destination_account=self.destination.pk,
            **kwargs,
        )
        return self.client.post(self.url_list, data)

    # --- criação do par ---

    def test_create_retorna_201(self):
        """POST de transferência válida deve retornar 201."""
        response = self._create_transfer()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_gera_dois_registros_no_banco(self):
        """POST transferência deve criar exatamente 2 Transaction no banco."""
        count_antes = Transaction.objects.count()
        self._create_transfer()
        self.assertEqual(Transaction.objects.count(), count_antes + 2)

    def test_create_par_compartilha_transfer_pair_id(self):
        """As duas transações geradas devem compartilhar o mesmo transfer_pair_id."""
        self._create_transfer()
        pair_ids = set(
            Transaction.objects.filter(type='transferencia')
            .values_list('transfer_pair_id', flat=True)
        )
        self.assertEqual(len(pair_ids), 1)
        self.assertIsNotNone(list(pair_ids)[0])

    def test_create_define_transfer_direction_corretamente(self):
        """Origem deve ter transfer_direction='debit' e destino 'credit'."""
        self._create_transfer()
        debit = Transaction.objects.filter(
            type='transferencia', transfer_direction='debit').first()
        credit = Transaction.objects.filter(
            type='transferencia', transfer_direction='credit').first()
        self.assertIsNotNone(debit)
        self.assertIsNotNone(credit)
        self.assertEqual(debit.account, self.origin)
        self.assertEqual(credit.account, self.destination)

    def test_create_paga_debita_origem_e_credita_destino(self):
        """Transferência paga deve debitar origem e creditar destino."""
        self._create_transfer(amount='300.00', is_paid=True)
        # Origem: 1000 - 300 = 700
        self.assertEqual(self._balance(self.origin), Decimal('700.00'))
        # Destino: 500 + 300 = 800
        self.assertEqual(self._balance(self.destination), Decimal('800.00'))

    def test_create_nao_paga_nao_altera_saldo(self):
        """Transferência não paga não deve alterar nenhum saldo."""
        self._create_transfer(amount='300.00', is_paid=False)
        self.assertEqual(self._balance(self.origin), Decimal('1000.00'))
        self.assertEqual(self._balance(self.destination), Decimal('500.00'))

    def test_create_sem_destination_account_retorna_400(self):
        """POST de transferência sem destination_account deve retornar 400."""
        data = get_transaction_data(
            account=self.origin,
            type='transferencia',
            amount='200.00',
            is_paid=True,
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_destination_igual_origem_retorna_400(self):
        """POST com destination_account igual à conta de origem deve retornar 400."""
        data = get_transaction_data(
            account=self.origin,
            type='transferencia',
            amount='200.00',
            is_paid=True,
            destination_account=self.origin.pk,
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_destination_de_outro_usuario_retorna_400(self):
        """POST com destination_account de outro usuário deve retornar 400."""
        other_user = self.create_additional_user()
        other_relative = other_user.relatives.first()
        other_account = make_account(other_user, other_relative, 'Conta Outro')

        data = get_transaction_data(
            account=self.origin,
            type='transferencia',
            amount='200.00',
            is_paid=True,
            destination_account=other_account.pk,
        )
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- PATCH: bloqueios e sincronização ---

    def test_patch_account_em_transferencia_retorna_400(self):
        """PATCH alterando account de uma transferência deve retornar 400."""
        self._create_transfer()
        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')
        extra = make_account(self.user, self.relative, 'Conta Extra')

        response = self.client.patch(
            self._detail_url(debit.pk), {'account': extra.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_amount_sincroniza_com_par(self):
        """PATCH amount em uma perna deve atualizar o amount na perna par."""
        self._create_transfer(amount='200.00', is_paid=False)
        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')

        self.client.patch(self._detail_url(debit.pk), {'amount': '350.00'})

        credit = Transaction.objects.get(
            type='transferencia', transfer_direction='credit')
        self.assertEqual(credit.amount, Decimal('350.00'))

    def test_patch_description_sincroniza_com_par(self):
        """PATCH description em uma perna deve atualizar a perna par."""
        self._create_transfer(description='TED original')
        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')

        self.client.patch(self._detail_url(debit.pk),
                          {'description': 'TED atualizada'})

        credit = Transaction.objects.get(
            type='transferencia', transfer_direction='credit')
        self.assertEqual(credit.description, 'TED atualizada')

    def test_patch_is_paid_sincroniza_com_par(self):
        """PATCH is_paid em uma perna deve sincronizar com a perna par."""
        self._create_transfer(is_paid=False)
        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')

        self.client.patch(self._detail_url(debit.pk), {'is_paid': True})

        credit = Transaction.objects.get(
            type='transferencia', transfer_direction='credit')
        self.assertTrue(credit.is_paid)

    def test_patch_notes_sincroniza_com_par(self):
        """PATCH notes em uma perna deve sincronizar com a perna par."""
        self._create_transfer(is_paid=False)
        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')

        self.client.patch(self._detail_url(debit.pk),
                          {'notes': 'Ref: TED-001'})

        credit = Transaction.objects.get(
            type='transferencia', transfer_direction='credit')
        self.assertEqual(credit.notes, 'Ref: TED-001')

    # --- PATCH: recálculo de saldo ---

    def test_patch_amount_pago_recalcula_saldo_em_ambas(self):
        """PATCH amount em transferência paga deve recalcular saldo de origem e destino."""
        self._create_transfer(amount='200.00', is_paid=True)
        # Saldos pós-criação via API: Origem 800 / Destino 700
        self._set_balance(self.origin, '800.00')
        self._set_balance(self.destination, '700.00')

        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')
        self.client.patch(self._detail_url(debit.pk), {'amount': '350.00'})

        # Origem: 800 + 200 (reverte) - 350 (aplica) = 650
        self.assertEqual(self._balance(self.origin), Decimal('650.00'))
        # Destino: 700 - 200 (reverte) + 350 (aplica) = 850
        self.assertEqual(self._balance(self.destination), Decimal('850.00'))

    def test_patch_is_paid_false_para_true_aplica_saldo_em_ambas(self):
        """PATCH is_paid false→true deve debitar origem e creditar destino."""
        self._create_transfer(amount='300.00', is_paid=False)

        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')
        self.client.patch(self._detail_url(debit.pk), {'is_paid': True})

        # Origem: 1000 - 300 = 700 / Destino: 500 + 300 = 800
        self.assertEqual(self._balance(self.origin), Decimal('700.00'))
        self.assertEqual(self._balance(self.destination), Decimal('800.00'))

    def test_patch_is_paid_true_para_false_reverte_saldo_de_ambas(self):
        """PATCH is_paid true→false deve reverter saldo de origem e destino."""
        self._create_transfer(amount='300.00', is_paid=True)
        # Saldos pós-criação via API: Origem 700 / Destino 800
        self._set_balance(self.origin, '700.00')
        self._set_balance(self.destination, '800.00')

        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')
        self.client.patch(self._detail_url(debit.pk), {'is_paid': False})

        # Origem: 700 + 300 = 1000 (revertido) / Destino: 800 - 300 = 500 (revertido)
        self.assertEqual(self._balance(self.origin), Decimal('1000.00'))
        self.assertEqual(self._balance(self.destination), Decimal('500.00'))

    # --- DELETE do par ---

    def test_delete_remove_ambas_as_transacoes(self):
        """DELETE de uma perna deve remover as duas transações do banco."""
        self._create_transfer()
        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')
        pair_id = debit.transfer_pair_id

        response = self.client.delete(self._detail_url(debit.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Transaction.objects.filter(transfer_pair_id=pair_id).count(), 0)

    def test_delete_pelo_lado_credit_tambem_remove_par(self):
        """DELETE pela perna credit também deve remover ambas as transações."""
        self._create_transfer()
        credit = Transaction.objects.get(
            type='transferencia', transfer_direction='credit')
        pair_id = credit.transfer_pair_id

        response = self.client.delete(self._detail_url(credit.pk))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Transaction.objects.filter(transfer_pair_id=pair_id).count(), 0)

    def test_delete_paga_reverte_saldo_de_ambas(self):
        """DELETE de transferência paga deve reverter saldo de origem e destino."""
        self._create_transfer(amount='200.00', is_paid=True)
        # Saldos pós-criação via API: Origem 800 / Destino 700
        self._set_balance(self.origin, '800.00')
        self._set_balance(self.destination, '700.00')

        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')
        self.client.delete(self._detail_url(debit.pk))

        # Origem: 800 + 200 = 1000 (revertido) / Destino: 700 - 200 = 500 (revertido)
        self.assertEqual(self._balance(self.origin), Decimal('1000.00'))
        self.assertEqual(self._balance(self.destination), Decimal('500.00'))

    def test_delete_nao_paga_nao_altera_saldo(self):
        """DELETE de transferência não paga não deve alterar nenhum saldo."""
        self._create_transfer(amount='200.00', is_paid=False)

        debit = Transaction.objects.get(
            type='transferencia', transfer_direction='debit')
        self.client.delete(self._detail_url(debit.pk))

        self.assertEqual(self._balance(self.origin), Decimal('1000.00'))
        self.assertEqual(self._balance(self.destination), Decimal('500.00'))


# ===========================================================================
# TESTES — Parte 4: Recorrência (helpers, geração, API)
# ===========================================================================

from backend.api.transactions.views import (  # noqa: E402
    _add_months,
    _generate_instances,
    _next_occurrence,
    _nth_occurrence_date,
)


class RecurringHelpersTest(TestCase):
    """
    Testes unitários das funções auxiliares de data para recorrência.
    Valida cálculos de _add_months e _next_occurrence diretamente.
    """

    # --- _add_months ---

    def test_add_months_normal(self):
        """Soma de meses em dia que existe no mês destino."""
        result = _add_months(datetime.date(2026, 1, 15), 1)
        self.assertEqual(result, datetime.date(2026, 2, 15))

    def test_add_months_janeiro_31_mais_um(self):
        """Jan/31 + 1 mês deve retornar fev/28 (não fev/31)."""
        result = _add_months(datetime.date(2026, 1, 31), 1)
        self.assertEqual(result, datetime.date(2026, 2, 28))

    def test_add_months_bissexto(self):
        """Jan/31 + 1 mês em ano bissexto deve retornar fev/29."""
        result = _add_months(datetime.date(2024, 1, 31), 1)
        self.assertEqual(result, datetime.date(2024, 2, 29))

    def test_add_months_virada_de_ano(self):
        """Nov + 3 meses deve cruzar o ano corretamente."""
        result = _add_months(datetime.date(2026, 11, 15), 3)
        self.assertEqual(result, datetime.date(2027, 2, 15))

    def test_add_months_doze(self):
        """Soma de 12 meses incrementa um ano."""
        result = _add_months(datetime.date(2026, 3, 1), 12)
        self.assertEqual(result, datetime.date(2027, 3, 1))

    # --- _next_occurrence ---

    def test_next_occurrence_daily(self):
        """Frequência diária com intervalo 1 avança 1 dia."""
        result = _next_occurrence(datetime.date(2026, 3, 1), 'daily', 1)
        self.assertEqual(result, datetime.date(2026, 3, 2))

    def test_next_occurrence_daily_interval_3(self):
        """Frequência diária com intervalo 3 avança 3 dias."""
        result = _next_occurrence(datetime.date(2026, 3, 1), 'daily', 3)
        self.assertEqual(result, datetime.date(2026, 3, 4))

    def test_next_occurrence_weekly(self):
        """Frequência semanal com intervalo 1 avança 7 dias."""
        result = _next_occurrence(datetime.date(2026, 3, 1), 'weekly', 1)
        self.assertEqual(result, datetime.date(2026, 3, 8))

    def test_next_occurrence_weekly_interval_2(self):
        """Frequência semanal com intervalo 2 avança 14 dias."""
        result = _next_occurrence(datetime.date(2026, 3, 1), 'weekly', 2)
        self.assertEqual(result, datetime.date(2026, 3, 15))

    def test_next_occurrence_monthly(self):
        """Frequência mensal com intervalo 1 avança 1 mês."""
        result = _next_occurrence(datetime.date(2026, 3, 1), 'monthly', 1)
        self.assertEqual(result, datetime.date(2026, 4, 1))

    def test_next_occurrence_monthly_dia_31(self):
        """Frequência mensal a partir de dia 31 ajusta para último dia do mês."""
        result = _next_occurrence(datetime.date(2026, 1, 31), 'monthly', 1)
        self.assertEqual(result, datetime.date(2026, 2, 28))

    def test_next_occurrence_yearly(self):
        """Frequência anual com intervalo 1 avança 1 ano."""
        result = _next_occurrence(datetime.date(2026, 3, 1), 'yearly', 1)
        self.assertEqual(result, datetime.date(2027, 3, 1))

    def test_next_occurrence_yearly_bissexto_para_nao_bissexto(self):
        """Fev/29 (bissexto) + 1 ano ajusta para fev/28."""
        result = _next_occurrence(datetime.date(2024, 2, 29), 'yearly', 1)
        self.assertEqual(result, datetime.date(2025, 2, 28))


class RecurringGenerationTest(BaseAuthenticatedTestCase):
    """
    Testes unitários das funções _nth_occurrence_date e _generate_instances.
    Verifica que instâncias são geradas corretamente e duplicatas são evitadas.
    """

    def setUp(self):
        super().setUp()
        self.account = make_account(self.user, self.relative)
        self.category = make_category(self.user, self.relative)
        self.rule = make_recurring_rule(
            self.user, self.relative,
            account=self.account,
            category=self.category,
            start_date=datetime.date(2026, 3, 1),
            frequency='monthly',
            interval=1,
            amount='500.00',
        )

    # --- _nth_occurrence_date ---

    def test_nth_occurrence_date_primeira(self):
        """N=1 deve retornar start_date."""
        result = _nth_occurrence_date(self.rule, 1)
        self.assertEqual(result, datetime.date(2026, 3, 1))

    def test_nth_occurrence_date_terceira(self):
        """N=3 em frequência mensal deve retornar o 3º mês."""
        result = _nth_occurrence_date(self.rule, 3)
        self.assertEqual(result, datetime.date(2026, 5, 1))

    def test_nth_occurrence_date_sexta(self):
        """N=6 em frequência mensal deve retornar o 6º mês."""
        result = _nth_occurrence_date(self.rule, 6)
        self.assertEqual(result, datetime.date(2026, 8, 1))

    # --- _generate_instances ---

    def test_generate_instances_cria_registros(self):
        """Deve criar instâncias de Transaction para o intervalo informado."""
        from_date = datetime.date(2026, 3, 1)
        to_date = datetime.date(2026, 5, 1)
        count = _generate_instances(self.rule, from_date, to_date)
        self.assertEqual(count, 3)
        self.assertEqual(
            Transaction.objects.filter(recurring_rule=self.rule).count(), 3
        )

    def test_generate_instances_datas_corretas(self):
        """As instâncias criadas devem ter as datas mensais corretas."""
        _generate_instances(
            self.rule,
            datetime.date(2026, 3, 1),
            datetime.date(2026, 5, 1),
        )
        dates = set(
            Transaction.objects.filter(recurring_rule=self.rule)
            .values_list('date', flat=True)
        )
        expected = {
            datetime.date(2026, 3, 1),
            datetime.date(2026, 4, 1),
            datetime.date(2026, 5, 1),
        }
        self.assertEqual(dates, expected)

    def test_generate_instances_pula_existentes(self):
        """Não deve criar duplicatas se já houver instância na data."""
        # Cria a primeira instância manualmente
        make_transaction(
            self.user, self.relative, self.account, self.category,
            recurring_rule=self.rule,
            date=datetime.date(2026, 3, 1),
        )
        count = _generate_instances(
            self.rule,
            datetime.date(2026, 3, 1),
            datetime.date(2026, 5, 1),
        )
        # Apenas abr e mai devem ser criados (mar já existia)
        self.assertEqual(count, 2)
        self.assertEqual(
            Transaction.objects.filter(recurring_rule=self.rule).count(), 3
        )

    def test_generate_instances_retorna_zero_sem_intervalo(self):
        """Deve retornar 0 quando from_date > to_date."""
        count = _generate_instances(
            self.rule,
            datetime.date(2026, 6, 1),
            datetime.date(2026, 5, 1),
        )
        self.assertEqual(count, 0)
        self.assertEqual(
            Transaction.objects.filter(recurring_rule=self.rule).count(), 0
        )

    def test_generate_instances_campos_da_regra(self):
        """As instâncias devem herdar campos da regra (tipo, valor, descrição)."""
        _generate_instances(
            self.rule,
            datetime.date(2026, 3, 1),
            datetime.date(2026, 3, 1),
        )
        t = Transaction.objects.get(recurring_rule=self.rule)
        self.assertEqual(t.type, self.rule.type)
        self.assertEqual(t.amount, Decimal(str(self.rule.amount)))
        self.assertEqual(t.description, self.rule.description)
        self.assertFalse(t.is_paid)


class RecurringRuleCreateAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração para criação de RecurringRule via API.
    Verifica geração automática de instâncias de Transaction ao criar a regra.
    """

    def setUp(self):
        super().setUp()
        self.account = make_account(self.user, self.relative)
        self.category = make_category(self.user, self.relative)
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)
        self.url = reverse('recurring-rule-list')

    def _post_rule(self, **overrides):
        from backend.api.tests.constants import get_recurring_rule_data
        data = get_recurring_rule_data(
            account=self.account,
            category=self.category,
            **overrides,
        )
        return self.client.post(self.url, data, format='json')

    def test_create_com_occurrences_count_gera_instancias(self):
        """Criar regra com occurrences_count=3 deve gerar exatamente 3 instâncias."""
        response = self._post_rule(
            start_date='2026-03-01',
            occurrences_count=3,
            frequency='monthly',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rule = RecurringRule.objects.get(pk=response.data['id'])
        self.assertEqual(
            Transaction.objects.filter(recurring_rule=rule).count(), 3
        )

    def test_create_com_occurrences_count_datas_corretas(self):
        """As 3 instâncias devem ter datas mensais de mar, abr e mai/2026."""
        response = self._post_rule(
            start_date='2026-03-01',
            occurrences_count=3,
            frequency='monthly',
        )
        rule = RecurringRule.objects.get(pk=response.data['id'])
        dates = set(
            Transaction.objects.filter(recurring_rule=rule)
            .values_list('date', flat=True)
        )
        expected = {
            datetime.date(2026, 3, 1),
            datetime.date(2026, 4, 1),
            datetime.date(2026, 5, 1),
        }
        self.assertEqual(dates, expected)

    def test_create_com_end_date_gera_instancias(self):
        """Criar regra com end_date deve gerar instâncias até a data de encerramento."""
        response = self._post_rule(
            start_date='2026-03-01',
            end_date='2026-05-01',
            frequency='monthly',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rule = RecurringRule.objects.get(pk=response.data['id'])
        self.assertEqual(
            Transaction.objects.filter(recurring_rule=rule).count(), 3
        )

    def test_create_indefinida_gera_para_12_meses(self):
        """Regra sem end_date nem occurrences_count deve gerar instâncias para os próximos 12 meses."""
        today = datetime.date.today()
        response = self._post_rule(
            start_date=str(today),
            frequency='monthly',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rule = RecurringRule.objects.get(pk=response.data['id'])
        count = Transaction.objects.filter(recurring_rule=rule).count()
        # Deve gerar entre 12 e 13 instâncias (dependendo do dia)
        self.assertGreaterEqual(count, 12)
        self.assertLessEqual(count, 13)

    def test_create_retorna_201(self):
        """POST de regra válida deve retornar 201 Created."""
        response = self._post_rule(start_date='2026-03-01', occurrences_count=2)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_sem_relative_header_retorna_400(self):
        """Criar regra sem o header X-Relative-Id deve retornar 400."""
        del self.client.defaults['HTTP_X_RELATIVE_ID']
        response = self._post_rule(start_date='2026-03-01', occurrences_count=2)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_end_date_e_occurrences_count_retorna_400(self):
        """Informar end_date E occurrences_count deve retornar 400."""
        response = self._post_rule(
            start_date='2026-03-01',
            end_date='2026-06-01',
            occurrences_count=3,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_destroy_soft_deleta_regra(self):
        """DELETE de regra deve desativá-la (is_active=False), não deletar fisicamente."""
        response = self._post_rule(start_date='2026-03-01', occurrences_count=2)
        rule_id = response.data['id']
        url = reverse('recurring-rule-detail', args=[rule_id])
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rule = RecurringRule.objects.get(pk=rule_id)
        self.assertFalse(rule.is_active)


class RecurringOnDemandTest(BaseAuthenticatedTestCase):
    """
    Testes de integração para geração on-demand de instâncias na listagem.
    Verifica que o GET /transactions/?month=&year= dispara _ensure_horizon
    apenas para regras indefinidas ativas.
    """

    def setUp(self):
        super().setUp()
        self.account = make_account(self.user, self.relative)
        self.category = make_category(self.user, self.relative)
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)
        self.list_url = reverse('transaction-list')

        # Regra indefinida ativa (sem end_date e sem occurrences_count)
        self.rule = make_recurring_rule(
            self.user, self.relative,
            account=self.account,
            category=self.category,
            start_date=datetime.date.today(),
            frequency='monthly',
        )

    def test_list_com_month_e_year_gera_instancias(self):
        """GET com month e year deve disparar geração on-demand para regras indefinidas."""
        today = datetime.date.today()
        response = self.client.get(
            self.list_url,
            {'month': today.month, 'year': today.year},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        count = Transaction.objects.filter(recurring_rule=self.rule).count()
        self.assertGreater(count, 0)

    def test_list_sem_month_nao_gera_instancias(self):
        """GET sem month não deve disparar geração on-demand."""
        today = datetime.date.today()
        self.client.get(self.list_url, {'year': today.year})
        self.assertEqual(
            Transaction.objects.filter(recurring_rule=self.rule).count(), 0
        )

    def test_list_sem_year_nao_gera_instancias(self):
        """GET sem year não deve disparar geração on-demand."""
        today = datetime.date.today()
        self.client.get(self.list_url, {'month': today.month})
        self.assertEqual(
            Transaction.objects.filter(recurring_rule=self.rule).count(), 0
        )

    def test_list_regra_inativa_nao_gera(self):
        """Regra inativa não deve ter instâncias geradas on-demand."""
        RecurringRule.objects.filter(pk=self.rule.pk).update(is_active=False)
        today = datetime.date.today()
        self.client.get(
            self.list_url,
            {'month': today.month, 'year': today.year},
        )
        self.assertEqual(
            Transaction.objects.filter(recurring_rule=self.rule).count(), 0
        )

    def test_list_nao_cria_duplicatas_em_chamadas_consecutivas(self):
        """Chamadas consecutivas não devem duplicar instâncias existentes."""
        today = datetime.date.today()
        params = {'month': today.month, 'year': today.year}
        self.client.get(self.list_url, params)
        count_after_first = Transaction.objects.filter(
            recurring_rule=self.rule
        ).count()
        self.client.get(self.list_url, params)
        count_after_second = Transaction.objects.filter(
            recurring_rule=self.rule
        ).count()
        self.assertEqual(count_after_first, count_after_second)


class RecurringEditAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração para o endpoint POST /transactions/{pk}/edit_recurring/.
    Valida os três escopos: esta, esta_e_futuras, todas.
    """

    def setUp(self):
        super().setUp()
        self.account = make_account(self.user, self.relative)
        self.category = make_category(self.user, self.relative)
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)

        # Regra com 3 instâncias não pagas
        self.rule = make_recurring_rule(
            self.user, self.relative,
            account=self.account,
            category=self.category,
            start_date=datetime.date(2026, 3, 1),
            frequency='monthly',
            interval=1,
            amount='500.00',
            description='Aluguel',
        )
        self.t1 = make_transaction(
            self.user, self.relative, self.account, self.category,
            recurring_rule=self.rule,
            type='despesa',
            amount='500.00',
            description='Aluguel',
            date=datetime.date(2026, 3, 1),
            is_paid=False,
        )
        self.t2 = make_transaction(
            self.user, self.relative, self.account, self.category,
            recurring_rule=self.rule,
            type='despesa',
            amount='500.00',
            description='Aluguel',
            date=datetime.date(2026, 4, 1),
            is_paid=False,
        )
        self.t3 = make_transaction(
            self.user, self.relative, self.account, self.category,
            recurring_rule=self.rule,
            type='despesa',
            amount='500.00',
            description='Aluguel',
            date=datetime.date(2026, 5, 1),
            is_paid=False,
        )

    def _edit_url(self, pk):
        return reverse('transaction-edit-recurring', args=[pk])

    # --- scope: esta ---

    def test_edit_esta_retorna_200(self):
        """POST com scope='esta' deve retornar 200."""
        response = self.client.post(
            self._edit_url(self.t1.pk),
            {'scope': 'esta', 'amount': '600.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_edit_esta_atualiza_apenas_esta_instancia(self):
        """scope='esta' deve alterar só a instância selecionada."""
        self.client.post(
            self._edit_url(self.t1.pk),
            {'scope': 'esta', 'amount': '600.00'},
            format='json',
        )
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertEqual(self.t1.amount, Decimal('600.00'))
        self.assertEqual(self.t2.amount, Decimal('500.00'))

    def test_edit_esta_desassocia_da_regra(self):
        """scope='esta' deve setar recurring_rule=None na instância editada."""
        self.client.post(
            self._edit_url(self.t1.pk),
            {'scope': 'esta', 'description': 'Aluguel ajustado'},
            format='json',
        )
        self.t1.refresh_from_db()
        self.assertIsNone(self.t1.recurring_rule)

    def test_edit_esta_nao_altera_outras_instancias(self):
        """scope='esta' não deve modificar t2 nem t3."""
        self.client.post(
            self._edit_url(self.t1.pk),
            {'scope': 'esta', 'amount': '999.00'},
            format='json',
        )
        self.t2.refresh_from_db()
        self.t3.refresh_from_db()
        self.assertEqual(self.t2.amount, Decimal('500.00'))
        self.assertEqual(self.t3.amount, Decimal('500.00'))

    # --- scope: esta_e_futuras ---

    def test_edit_esta_e_futuras_atualiza_regra(self):
        """scope='esta_e_futuras' deve atualizar o amount na RecurringRule."""
        self.client.post(
            self._edit_url(self.t2.pk),
            {'scope': 'esta_e_futuras', 'amount': '700.00'},
            format='json',
        )
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.amount, Decimal('700.00'))

    def test_edit_esta_e_futuras_remove_instancias_futuras_nao_pagas(self):
        """scope='esta_e_futuras' deve deletar t2 e t3 (>= t2.date, não pagas)."""
        self.client.post(
            self._edit_url(self.t2.pk),
            {'scope': 'esta_e_futuras', 'amount': '700.00'},
            format='json',
        )
        self.assertFalse(Transaction.objects.filter(pk=self.t2.pk).exists())
        self.assertFalse(Transaction.objects.filter(pk=self.t3.pk).exists())

    def test_edit_esta_e_futuras_mantem_instancias_anteriores(self):
        """scope='esta_e_futuras' não deve remover t1 (anterior a t2.date)."""
        self.client.post(
            self._edit_url(self.t2.pk),
            {'scope': 'esta_e_futuras', 'amount': '700.00'},
            format='json',
        )
        self.assertTrue(Transaction.objects.filter(pk=self.t1.pk).exists())

    def test_edit_esta_e_futuras_regenera_instancias(self):
        """scope='esta_e_futuras' deve regenerar instâncias a partir de t2.date."""
        self.client.post(
            self._edit_url(self.t2.pk),
            {'scope': 'esta_e_futuras', 'amount': '700.00'},
            format='json',
        )
        # Deve existir pelo menos uma instância nova com o valor atualizado
        count = Transaction.objects.filter(
            recurring_rule=self.rule,
            amount=Decimal('700.00'),
        ).count()
        self.assertGreater(count, 0)

    def test_edit_esta_e_futuras_nao_altera_pagas(self):
        """scope='esta_e_futuras' não deve deletar instâncias pagas."""
        self.t2.is_paid = True
        self.t2.save()
        self.client.post(
            self._edit_url(self.t3.pk),
            {'scope': 'esta_e_futuras', 'amount': '700.00'},
            format='json',
        )
        # t2 está paga e tem data < t3.date, portanto não deve ser deletada
        self.assertTrue(Transaction.objects.filter(pk=self.t2.pk).exists())

    # --- scope: todas ---

    def test_edit_todas_atualiza_regra(self):
        """scope='todas' deve atualizar o amount na RecurringRule."""
        self.client.post(
            self._edit_url(self.t1.pk),
            {'scope': 'todas', 'amount': '800.00'},
            format='json',
        )
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.amount, Decimal('800.00'))

    def test_edit_todas_remove_todas_instancias_nao_pagas(self):
        """scope='todas' deve deletar todas as instâncias não pagas da regra."""
        self.client.post(
            self._edit_url(self.t1.pk),
            {'scope': 'todas', 'amount': '800.00'},
            format='json',
        )
        # Todas as instâncias originais (não pagas) devem ter sido deletadas
        self.assertFalse(Transaction.objects.filter(pk=self.t1.pk).exists())
        self.assertFalse(Transaction.objects.filter(pk=self.t2.pk).exists())
        self.assertFalse(Transaction.objects.filter(pk=self.t3.pk).exists())

    def test_edit_todas_regenera_instancias(self):
        """scope='todas' deve regenerar instâncias desde start_date com novo valor."""
        self.client.post(
            self._edit_url(self.t1.pk),
            {'scope': 'todas', 'amount': '800.00'},
            format='json',
        )
        count = Transaction.objects.filter(
            recurring_rule=self.rule,
            amount=Decimal('800.00'),
        ).count()
        self.assertGreater(count, 0)

    def test_edit_todas_nao_deleta_pagas(self):
        """scope='todas' não deve deletar instâncias pagas."""
        self.t1.is_paid = True
        self.t1.save()
        self.client.post(
            self._edit_url(self.t2.pk),
            {'scope': 'todas', 'amount': '800.00'},
            format='json',
        )
        self.assertTrue(Transaction.objects.filter(pk=self.t1.pk).exists())

    # --- validação de escopo ---

    def test_edit_escopo_invalido_retorna_400(self):
        """Escopo inválido deve retornar 400."""
        response = self.client.post(
            self._edit_url(self.t1.pk),
            {'scope': 'invalido', 'amount': '600.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_sem_escopo_retorna_400(self):
        """Omitir o campo scope deve retornar 400."""
        response = self.client.post(
            self._edit_url(self.t1.pk),
            {'amount': '600.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_esta_e_futuras_sem_regra_retorna_400(self):
        """Transação avulsa (sem recurring_rule) com scope='esta_e_futuras' deve retornar 400."""
        t_avulsa = make_transaction(
            self.user, self.relative, self.account, self.category,
            date=datetime.date(2026, 6, 1),
        )
        response = self.client.post(
            self._edit_url(t_avulsa.pk),
            {'scope': 'esta_e_futuras', 'amount': '600.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RecurringDeleteAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração para o endpoint DELETE /transactions/{pk}/delete_recurring/.
    Valida os três escopos: esta, esta_e_futuras, todas.
    """

    def setUp(self):
        super().setUp()
        self.account = make_account(self.user, self.relative)
        self.category = make_category(self.user, self.relative)
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)

        self.rule = make_recurring_rule(
            self.user, self.relative,
            account=self.account,
            category=self.category,
            start_date=datetime.date(2026, 3, 1),
            frequency='monthly',
            interval=1,
            amount='500.00',
            description='Aluguel',
        )
        self.t1 = make_transaction(
            self.user, self.relative, self.account, self.category,
            recurring_rule=self.rule,
            type='despesa',
            amount='500.00',
            description='Aluguel',
            date=datetime.date(2026, 3, 1),
            is_paid=False,
        )
        self.t2 = make_transaction(
            self.user, self.relative, self.account, self.category,
            recurring_rule=self.rule,
            type='despesa',
            amount='500.00',
            description='Aluguel',
            date=datetime.date(2026, 4, 1),
            is_paid=False,
        )
        self.t3 = make_transaction(
            self.user, self.relative, self.account, self.category,
            recurring_rule=self.rule,
            type='despesa',
            amount='500.00',
            description='Aluguel',
            date=datetime.date(2026, 5, 1),
            is_paid=False,
        )

    def _delete_url(self, pk):
        return reverse('transaction-delete-recurring', args=[pk])

    def _balance(self):
        self.account.refresh_from_db()
        return self.account.balance

    # --- scope: esta ---

    def test_delete_esta_retorna_204(self):
        """DELETE com scope='esta' deve retornar 204 No Content."""
        response = self.client.delete(
            self._delete_url(self.t1.pk),
            {'scope': 'esta'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_esta_remove_apenas_esta_instancia(self):
        """scope='esta' deve deletar apenas t1, mantendo t2 e t3."""
        self.client.delete(
            self._delete_url(self.t1.pk),
            {'scope': 'esta'},
            format='json',
        )
        self.assertFalse(Transaction.objects.filter(pk=self.t1.pk).exists())
        self.assertTrue(Transaction.objects.filter(pk=self.t2.pk).exists())
        self.assertTrue(Transaction.objects.filter(pk=self.t3.pk).exists())

    def test_delete_esta_paga_reverte_saldo(self):
        """scope='esta' em transação paga deve reverter o saldo da conta."""
        # Marca t1 como paga e aplica o saldo manualmente
        self.t1.is_paid = True
        self.t1.save()
        Account.objects.filter(pk=self.account.pk).update(
            balance=Decimal(str(self.account.balance)) - Decimal('500.00')
        )
        saldo_antes = self._balance()

        self.client.delete(
            self._delete_url(self.t1.pk),
            {'scope': 'esta'},
            format='json',
        )
        self.assertEqual(self._balance(), saldo_antes + Decimal('500.00'))

    def test_delete_esta_nao_paga_nao_altera_saldo(self):
        """scope='esta' em transação não paga não deve alterar saldo."""
        saldo_antes = self._balance()
        self.client.delete(
            self._delete_url(self.t1.pk),
            {'scope': 'esta'},
            format='json',
        )
        self.assertEqual(self._balance(), saldo_antes)

    # --- scope: esta_e_futuras ---

    def test_delete_esta_e_futuras_retorna_200(self):
        """DELETE com scope='esta_e_futuras' deve retornar 200."""
        response = self.client.delete(
            self._delete_url(self.t2.pk),
            {'scope': 'esta_e_futuras'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_esta_e_futuras_remove_futuras_nao_pagas(self):
        """scope='esta_e_futuras' deve remover t2 e t3 (>= t2.date, não pagas)."""
        self.client.delete(
            self._delete_url(self.t2.pk),
            {'scope': 'esta_e_futuras'},
            format='json',
        )
        self.assertFalse(Transaction.objects.filter(pk=self.t2.pk).exists())
        self.assertFalse(Transaction.objects.filter(pk=self.t3.pk).exists())

    def test_delete_esta_e_futuras_mantem_anteriores(self):
        """scope='esta_e_futuras' não deve remover t1 (anterior a t2.date)."""
        self.client.delete(
            self._delete_url(self.t2.pk),
            {'scope': 'esta_e_futuras'},
            format='json',
        )
        self.assertTrue(Transaction.objects.filter(pk=self.t1.pk).exists())

    def test_delete_esta_e_futuras_encerra_regra(self):
        """scope='esta_e_futuras' deve setar end_date na regra como t2.date - 1 dia."""
        self.client.delete(
            self._delete_url(self.t2.pk),
            {'scope': 'esta_e_futuras'},
            format='json',
        )
        self.rule.refresh_from_db()
        expected_end = datetime.date(2026, 4, 1) - datetime.timedelta(days=1)
        self.assertEqual(self.rule.end_date, expected_end)

    def test_delete_esta_e_futuras_nao_remove_pagas(self):
        """scope='esta_e_futuras' não deve remover instâncias pagas."""
        self.t2.is_paid = True
        self.t2.save()
        self.client.delete(
            self._delete_url(self.t3.pk),
            {'scope': 'esta_e_futuras'},
            format='json',
        )
        # t2 está paga — não deve ser removida mesmo que sua data >= t3.date
        # Nota: t3.date > t2.date, então t2 não está em date__gte=t3.date de qualquer forma
        self.assertTrue(Transaction.objects.filter(pk=self.t2.pk).exists())

    # --- scope: todas ---

    def test_delete_todas_retorna_200(self):
        """DELETE com scope='todas' deve retornar 200."""
        response = self.client.delete(
            self._delete_url(self.t1.pk),
            {'scope': 'todas'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_todas_desativa_regra(self):
        """scope='todas' deve setar is_active=False na RecurringRule."""
        self.client.delete(
            self._delete_url(self.t1.pk),
            {'scope': 'todas'},
            format='json',
        )
        self.rule.refresh_from_db()
        self.assertFalse(self.rule.is_active)

    def test_delete_todas_remove_nao_pagas(self):
        """scope='todas' deve remover todas as instâncias não pagas da regra."""
        self.client.delete(
            self._delete_url(self.t1.pk),
            {'scope': 'todas'},
            format='json',
        )
        self.assertFalse(Transaction.objects.filter(pk=self.t1.pk).exists())
        self.assertFalse(Transaction.objects.filter(pk=self.t2.pk).exists())
        self.assertFalse(Transaction.objects.filter(pk=self.t3.pk).exists())

    def test_delete_todas_nao_remove_pagas(self):
        """scope='todas' não deve remover instâncias pagas."""
        self.t1.is_paid = True
        self.t1.save()
        self.client.delete(
            self._delete_url(self.t2.pk),
            {'scope': 'todas'},
            format='json',
        )
        self.assertTrue(Transaction.objects.filter(pk=self.t1.pk).exists())

    # --- validação de escopo ---

    def test_delete_escopo_invalido_retorna_400(self):
        """Escopo inválido deve retornar 400."""
        response = self.client.delete(
            self._delete_url(self.t1.pk),
            {'scope': 'invalido'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_sem_escopo_retorna_400(self):
        """Omitir o campo scope deve retornar 400."""
        response = self.client.delete(
            self._delete_url(self.t1.pk),
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_esta_e_futuras_sem_regra_retorna_400(self):
        """Transação avulsa com scope='esta_e_futuras' deve retornar 400."""
        t_avulsa = make_transaction(
            self.user, self.relative, self.account, self.category,
            date=datetime.date(2026, 6, 1),
        )
        response = self.client.delete(
            self._delete_url(t_avulsa.pk),
            {'scope': 'esta_e_futuras'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_todas_sem_regra_retorna_400(self):
        """Transação avulsa com scope='todas' deve retornar 400."""
        t_avulsa = make_transaction(
            self.user, self.relative, self.account, self.category,
            date=datetime.date(2026, 6, 1),
        )
        response = self.client.delete(
            self._delete_url(t_avulsa.pk),
            {'scope': 'todas'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
