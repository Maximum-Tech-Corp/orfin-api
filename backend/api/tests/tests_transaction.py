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
        """POST com transferência sem categoria deve retornar 201."""
        # transferencia não precisa de category — não passamos category aqui
        data = get_transaction_data(
            account=self.account,
            type='transferencia',
            description='TED para poupança',
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
