import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from backend.api.accounts.models import Account
from backend.api.credit_cards.models import CreditCard, Invoice, get_or_create_invoice
from backend.api.transactions.models import Transaction

from .base import BaseAuthenticatedTestCase
from .constants import get_user_data


# ---------------------------------------------------------------------------
# Helpers de fixture compartilhados
# ---------------------------------------------------------------------------


def make_credit_card(user, relative, name='Nubank', closing_day=10, due_day=15, **kwargs):
    """Cria um CreditCard mínimo para uso nos testes."""
    defaults = {
        'color': '#8A05BE',
        'limit': Decimal('5000.00'),
        'closing_day': closing_day,
        'due_day': due_day,
    }
    defaults.update(kwargs)
    return CreditCard.objects.create(
        user=user,
        relative=relative,
        name=name,
        **defaults,
    )


def make_invoice(credit_card, reference_month, reference_year, **kwargs):
    """Cria uma Invoice mínima para uso nos testes."""
    defaults = {
        'status': 'aberta',
        'due_date': datetime.date(reference_year, reference_month, credit_card.due_day),
        'total_amount': Decimal('0'),
    }
    defaults.update(kwargs)
    return Invoice.objects.create(
        credit_card=credit_card,
        reference_month=reference_month,
        reference_year=reference_year,
        **defaults,
    )


# ===========================================================================
# TESTES DE MODEL — CreditCard
# ===========================================================================

class CreditCardModelTest(BaseAuthenticatedTestCase):
    """
    Testes unitários do model CreditCard.
    Valida regras de negócio no nível do banco (clean/save).
    """

    def test_create_valido(self):
        """Criar cartão com dados válidos não deve lançar exceção."""
        card = make_credit_card(self.user, self.relative)
        self.assertIsNotNone(card.pk)

    def test_closing_day_invalido_abaixo_de_1(self):
        """closing_day=0 deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            make_credit_card(self.user, self.relative, name='C1', closing_day=0)

    def test_closing_day_invalido_acima_de_28(self):
        """closing_day=29 deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            make_credit_card(self.user, self.relative, name='C2', closing_day=29)

    def test_due_day_invalido_abaixo_de_1(self):
        """due_day=0 deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            make_credit_card(self.user, self.relative, name='C3', due_day=0)

    def test_due_day_invalido_acima_de_28(self):
        """due_day=29 deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            make_credit_card(self.user, self.relative, name='C4', due_day=29)

    def test_limit_negativo(self):
        """limit negativo deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            make_credit_card(self.user, self.relative, name='C5', limit=Decimal('-100.00'))

    def test_limit_zero(self):
        """limit=0 deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            make_credit_card(self.user, self.relative, name='C6', limit=Decimal('0'))

    def test_soft_delete_arquiva_cartao(self):
        """soft_delete() deve setar is_archived=True sem deletar o registro."""
        card = make_credit_card(self.user, self.relative)
        card.soft_delete()
        card.refresh_from_db()
        self.assertTrue(card.is_archived)
        self.assertTrue(CreditCard.objects.filter(pk=card.pk).exists())

    def test_delete_fisico_raises_not_implemented(self):
        """delete() direto deve lançar NotImplementedError."""
        card = make_credit_card(self.user, self.relative)
        with self.assertRaises(NotImplementedError):
            card.delete()

    def test_str_representation(self):
        """__str__ deve conter o nome e o dia de fechamento."""
        card = make_credit_card(self.user, self.relative, name='Itaú', closing_day=5)
        self.assertIn('Itaú', str(card))
        self.assertIn('5', str(card))


# ===========================================================================
# TESTES DE MODEL — Invoice
# ===========================================================================

class InvoiceModelTest(BaseAuthenticatedTestCase):
    """
    Testes unitários do model Invoice.
    Valida update_status() e recalculate_total().
    """

    def setUp(self):
        super().setUp()
        self.card = make_credit_card(self.user, self.relative, closing_day=10, due_day=15)

    def test_update_status_fecha_fatura_expirada(self):
        """
        Fatura cujo closing_date já passou deve ter status atualizado para 'fechada'.
        Usa mês/ano passado para garantir que a data de fechamento já ocorreu.
        """
        invoice = make_invoice(self.card, 1, 2026, status='aberta')
        invoice.update_status()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'fechada')

    def test_update_status_nao_altera_paga(self):
        """Fatura com status='paga' não deve ter o status alterado."""
        invoice = make_invoice(self.card, 1, 2026, status='paga')
        invoice.update_status()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'paga')

    def test_update_status_nao_altera_fechada(self):
        """Fatura já fechada não deve ter o status alterado novamente."""
        invoice = make_invoice(self.card, 1, 2026, status='fechada')
        invoice.update_status()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'fechada')

    def test_update_status_nao_fecha_fatura_futura(self):
        """Fatura com closing_date no futuro não deve ser fechada."""
        # Fatura para daqui 2 anos — closing_date ainda não chegou
        ano_futuro = datetime.date.today().year + 2
        invoice = make_invoice(self.card, 1, ano_futuro, status='aberta')
        invoice.update_status()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'aberta')

    def test_recalculate_total_sem_transacoes(self):
        """recalculate_total() com nenhuma transação vinculada deve resultar em 0."""
        invoice = make_invoice(self.card, 3, 2026)
        invoice.recalculate_total()
        invoice.refresh_from_db()
        self.assertEqual(invoice.total_amount, Decimal('0'))

    def test_str_representation(self):
        """__str__ deve conter mês, ano e nome do cartão."""
        invoice = make_invoice(self.card, 3, 2026)
        s = str(invoice)
        self.assertIn('03', s)
        self.assertIn('2026', s)
        self.assertIn('Nubank', s)


# ===========================================================================
# TESTES DE MODEL — get_or_create_invoice
# ===========================================================================

class GetOrCreateInvoiceTest(BaseAuthenticatedTestCase):
    """
    Testes unitários do helper get_or_create_invoice().
    Valida a lógica de determinação da fatura correta com base no closing_day.
    """

    def setUp(self):
        super().setUp()
        # Cartão com fechamento no dia 10
        self.card = make_credit_card(
            self.user, self.relative, closing_day=10, due_day=15
        )

    def test_data_antes_do_fechamento_vai_para_mes_corrente(self):
        """Transação no dia 5 (antes do fechamento dia 10) → fatura do mesmo mês."""
        invoice = get_or_create_invoice(self.card, datetime.date(2026, 3, 5))
        self.assertEqual(invoice.reference_month, 3)
        self.assertEqual(invoice.reference_year, 2026)

    def test_data_no_dia_do_fechamento_vai_para_mes_corrente(self):
        """Transação exatamente no dia do fechamento (dia 10) → fatura do mesmo mês."""
        invoice = get_or_create_invoice(self.card, datetime.date(2026, 3, 10))
        self.assertEqual(invoice.reference_month, 3)
        self.assertEqual(invoice.reference_year, 2026)

    def test_data_apos_fechamento_vai_para_proximo_mes(self):
        """Transação no dia 11 (após fechamento dia 10) → fatura do próximo mês."""
        invoice = get_or_create_invoice(self.card, datetime.date(2026, 3, 11))
        self.assertEqual(invoice.reference_month, 4)
        self.assertEqual(invoice.reference_year, 2026)

    def test_data_em_dezembro_apos_fechamento_vai_para_janeiro_proximo_ano(self):
        """Transação em dez após fechamento → fatura de jan do próximo ano."""
        invoice = get_or_create_invoice(self.card, datetime.date(2026, 12, 15))
        self.assertEqual(invoice.reference_month, 1)
        self.assertEqual(invoice.reference_year, 2027)

    def test_data_em_dezembro_antes_do_fechamento(self):
        """Transação em dez antes do fechamento → fatura de dez do mesmo ano."""
        invoice = get_or_create_invoice(self.card, datetime.date(2026, 12, 5))
        self.assertEqual(invoice.reference_month, 12)
        self.assertEqual(invoice.reference_year, 2026)

    def test_cria_fatura_automaticamente(self):
        """Deve criar a Invoice se ainda não existir."""
        self.assertEqual(Invoice.objects.count(), 0)
        get_or_create_invoice(self.card, datetime.date(2026, 3, 5))
        self.assertEqual(Invoice.objects.count(), 1)

    def test_nao_duplica_fatura_existente(self):
        """Chamadas consecutivas para o mesmo mês/ano devem retornar a mesma Invoice."""
        inv1 = get_or_create_invoice(self.card, datetime.date(2026, 3, 5))
        inv2 = get_or_create_invoice(self.card, datetime.date(2026, 3, 1))
        self.assertEqual(inv1.pk, inv2.pk)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_due_date_calculada_corretamente(self):
        """A due_date da fatura criada deve usar o due_day do cartão."""
        invoice = get_or_create_invoice(self.card, datetime.date(2026, 3, 5))
        self.assertEqual(invoice.due_date, datetime.date(2026, 3, 15))

    def test_due_day_ajustado_para_ultimo_dia_do_mes(self):
        """due_day ajustado quando o mês tem menos dias (ex: due_day=31 em fevereiro)."""
        card = make_credit_card(
            self.user, self.relative, name='Card28', closing_day=25, due_day=28
        )
        invoice = get_or_create_invoice(card, datetime.date(2026, 1, 20))
        # Fatura de jan, due_day=28 → 28/01 é válido
        self.assertEqual(invoice.due_date.day, 28)


# ===========================================================================
# TESTES DE API — CreditCard CRUD
# ===========================================================================

class CreditCardAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração para o CreditCardViewSet.
    Cobre CRUD, filtros, soft delete, unarchive e listagem de faturas.
    """

    def setUp(self):
        super().setUp()
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)
        self.list_url = reverse('credit-card-list')

    def _detail_url(self, pk):
        return reverse('credit-card-detail', args=[pk])

    def _valid_data(self, **overrides):
        data = {
            'name': 'Nubank',
            'color': '#8A05BE',
            'limit': '5000.00',
            'closing_day': 10,
            'due_day': 15,
        }
        data.update(overrides)
        return data

    # --- Criação ---

    def test_create_retorna_201(self):
        """POST com dados válidos deve retornar 201 Created."""
        response = self.client.post(self.list_url, self._valid_data())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_persiste_campos(self):
        """POST deve persistir todos os campos corretamente."""
        self.client.post(self.list_url, self._valid_data())
        card = CreditCard.objects.get(name='Nubank')
        self.assertEqual(card.closing_day, 10)
        self.assertEqual(card.due_day, 15)
        self.assertEqual(card.limit, Decimal('5000.00'))
        self.assertEqual(card.user, self.user)
        self.assertEqual(card.relative, self.relative)

    def test_create_sem_relative_header_retorna_400(self):
        """POST sem X-Relative-Id deve retornar 400."""
        del self.client.defaults['HTTP_X_RELATIVE_ID']
        response = self.client.post(self.list_url, self._valid_data())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_nome_duplicado_retorna_400(self):
        """POST com nome duplicado no mesmo perfil deve retornar 400."""
        make_credit_card(self.user, self.relative, name='Nubank')
        response = self.client.post(self.list_url, self._valid_data(name='Nubank'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('nome', str(response.data).lower())

    def test_create_closing_day_invalido_retorna_400(self):
        """POST com closing_day=29 deve retornar 400."""
        response = self.client.post(self.list_url, self._valid_data(closing_day=29))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_due_day_invalido_retorna_400(self):
        """POST com due_day=0 deve retornar 400."""
        response = self.client.post(self.list_url, self._valid_data(due_day=0))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_limit_negativo_retorna_400(self):
        """POST com limit negativo deve retornar 400."""
        response = self.client.post(self.list_url, self._valid_data(limit='-100'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_cor_invalida_retorna_400(self):
        """POST com cor fora do formato #RRGGBB deve retornar 400."""
        response = self.client.post(self.list_url, self._valid_data(color='azul'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Listagem ---

    def test_list_retorna_apenas_ativos(self):
        """GET /credit-cards/ deve retornar apenas cartões não arquivados."""
        make_credit_card(self.user, self.relative, name='Ativo')
        card_arq = make_credit_card(self.user, self.relative, name='Arquivado')
        card_arq.soft_delete()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nomes = [r['name'] for r in response.data['results']]
        self.assertIn('Ativo', nomes)
        self.assertNotIn('Arquivado', nomes)

    def test_list_only_archived_retorna_arquivados(self):
        """GET com ?only_archived=true deve retornar apenas cartões arquivados."""
        make_credit_card(self.user, self.relative, name='Ativo')
        card_arq = make_credit_card(self.user, self.relative, name='Arquivado')
        card_arq.soft_delete()
        response = self.client.get(self.list_url, {'only_archived': 'true'})
        nomes = [r['name'] for r in response.data['results']]
        self.assertIn('Arquivado', nomes)
        self.assertNotIn('Ativo', nomes)

    def test_list_sem_relative_header_retorna_lista_vazia(self):
        """GET sem X-Relative-Id não deve filtrar por perfil — retorna cartões do usuário."""
        make_credit_card(self.user, self.relative, name='Nu')
        del self.client.defaults['HTTP_X_RELATIVE_ID']
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_nao_retorna_cartoes_de_outro_usuario(self):
        """GET não deve retornar cartões de outros usuários."""
        outro_user = self.create_additional_user('2')
        outro_relative = outro_user.relatives.first()
        make_credit_card(outro_user, outro_relative, name='CartaoAlheio')
        response = self.client.get(self.list_url)
        nomes = [r['name'] for r in response.data['results']]
        self.assertNotIn('CartaoAlheio', nomes)

    # --- Detalhe e Update ---

    def test_retrieve_retorna_200(self):
        """GET /credit-cards/{id}/ deve retornar 200."""
        card = make_credit_card(self.user, self.relative)
        response = self.client.get(self._detail_url(card.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_cartao_alheio_retorna_404(self):
        """GET de cartão de outro usuário deve retornar 404."""
        outro_user = self.create_additional_user('2')
        outro_relative = outro_user.relatives.first()
        card = make_credit_card(outro_user, outro_relative)
        response = self.client.get(self._detail_url(card.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_atualiza_nome(self):
        """PATCH deve atualizar o nome do cartão."""
        card = make_credit_card(self.user, self.relative)
        response = self.client.patch(
            self._detail_url(card.pk), {'name': 'Bradesco'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        card.refresh_from_db()
        self.assertEqual(card.name, 'Bradesco')

    # --- Soft delete ---

    def test_destroy_arquiva_cartao(self):
        """DELETE deve arquivar o cartão (soft delete) retornando 200."""
        card = make_credit_card(self.user, self.relative)
        response = self.client.delete(self._detail_url(card.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        card.refresh_from_db()
        self.assertTrue(card.is_archived)

    def test_destroy_nao_deleta_fisicamente(self):
        """DELETE não deve remover o registro do banco."""
        card = make_credit_card(self.user, self.relative)
        self.client.delete(self._detail_url(card.pk))
        self.assertTrue(CreditCard.objects.filter(pk=card.pk).exists())

    # --- Unarchive ---

    def test_unarchive_retorna_200(self):
        """POST /unarchive/ em cartão arquivado deve retornar 200."""
        card = make_credit_card(self.user, self.relative)
        card.soft_delete()
        url = reverse('credit-card-unarchive', args=[card.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unarchive_restaura_cartao(self):
        """POST /unarchive/ deve setar is_archived=False."""
        card = make_credit_card(self.user, self.relative)
        card.soft_delete()
        url = reverse('credit-card-unarchive', args=[card.pk])
        self.client.post(url)
        card.refresh_from_db()
        self.assertFalse(card.is_archived)

    def test_unarchive_cartao_ativo_retorna_400(self):
        """POST /unarchive/ em cartão não arquivado deve retornar 400."""
        card = make_credit_card(self.user, self.relative)
        url = reverse('credit-card-unarchive', args=[card.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Listagem de faturas ---

    def test_invoices_retorna_faturas_do_cartao(self):
        """GET /credit-cards/{id}/invoices/ deve listar as faturas do cartão."""
        card = make_credit_card(self.user, self.relative)
        make_invoice(card, 3, 2026)
        make_invoice(card, 4, 2026)
        url = reverse('credit-card-invoices', args=[card.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_invoices_nao_retorna_faturas_de_outro_cartao(self):
        """GET /invoices/ não deve misturar faturas de cartões diferentes."""
        card1 = make_credit_card(self.user, self.relative, name='C1')
        card2 = make_credit_card(self.user, self.relative, name='C2')
        make_invoice(card1, 3, 2026)
        make_invoice(card2, 3, 2026)
        url = reverse('credit-card-invoices', args=[card1.pk])
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)

    def test_invoices_fecha_faturas_expiradas_lazy(self):
        """GET /invoices/ deve fechar automaticamente faturas cujo período já passou."""
        card = make_credit_card(self.user, self.relative)
        # Fatura de jan/2026 — closing_date já passou
        inv = make_invoice(card, 1, 2026, status='aberta')
        url = reverse('credit-card-invoices', args=[card.pk])
        self.client.get(url)
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'fechada')

    def test_invoices_retorna_200_sem_faturas(self):
        """GET /invoices/ em cartão sem faturas deve retornar lista vazia."""
        card = make_credit_card(self.user, self.relative)
        url = reverse('credit-card-invoices', args=[card.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    # --- Autenticação ---

    def test_nao_autenticado_retorna_401(self):
        """Requisições sem autenticação devem retornar 401."""
        self.unauthenticate()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_relative_id_invalido_retorna_400(self):
        """
        POST /credit-cards/ com X-Relative-Id com ID inexistente deve retornar 400.
        Cobre o bloco except Relative.DoesNotExist em CreditCardSerializer.create().
        """
        self.client.defaults['HTTP_X_RELATIVE_ID'] = '999999'
        response = self.client.post(self.list_url, self._valid_data())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_relative_id_invalido_retorna_400(self):
        """
        GET /credit-cards/ com X-Relative-Id com ID inexistente deve retornar 400.
        Cobre o bloco except Relative.DoesNotExist em CreditCardViewSet.get_queryset().
        """
        self.client.defaults['HTTP_X_RELATIVE_ID'] = '999999'
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# TESTES DE API — Invoice (retrieve)
# ===========================================================================

class InvoiceAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração para o InvoiceViewSet.
    Cobre GET detail e atualização lazy de status.
    """

    def setUp(self):
        super().setUp()
        self.card = make_credit_card(self.user, self.relative)

    def _detail_url(self, pk):
        return reverse('invoice-detail', args=[pk])

    def test_retrieve_retorna_200(self):
        """GET /invoices/{id}/ deve retornar 200 com os campos da fatura."""
        invoice = make_invoice(self.card, 3, 2026)
        response = self.client.get(self._detail_url(invoice.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['reference_month'], 3)
        self.assertEqual(response.data['reference_year'], 2026)

    def test_retrieve_inclui_credit_card_name(self):
        """GET deve incluir o nome do cartão no campo credit_card_name."""
        invoice = make_invoice(self.card, 3, 2026)
        response = self.client.get(self._detail_url(invoice.pk))
        self.assertEqual(response.data['credit_card_name'], self.card.name)

    def test_retrieve_fecha_fatura_expirada_lazy(self):
        """GET deve fechar automaticamente fatura com período encerrado."""
        invoice = make_invoice(self.card, 1, 2026, status='aberta')
        self.client.get(self._detail_url(invoice.pk))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'fechada')

    def test_retrieve_nao_altera_fatura_paga(self):
        """GET não deve alterar o status de fatura paga."""
        invoice = make_invoice(self.card, 1, 2026, status='paga')
        self.client.get(self._detail_url(invoice.pk))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'paga')

    def test_retrieve_fatura_de_outro_usuario_retorna_404(self):
        """GET de fatura de outro usuário deve retornar 404."""
        outro_user = self.create_additional_user('2')
        outro_relative = outro_user.relatives.first()
        outro_card = make_credit_card(outro_user, outro_relative)
        invoice = make_invoice(outro_card, 3, 2026)
        response = self.client.get(self._detail_url(invoice.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nao_autenticado_retorna_401(self):
        """GET sem autenticação deve retornar 401."""
        invoice = make_invoice(self.card, 3, 2026)
        self.unauthenticate()
        response = self.client.get(self._detail_url(invoice.pk))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ===========================================================================
# TESTES DE MODEL — Transaction XOR constraint (account XOR invoice)
# ===========================================================================

class TransactionXORConstraintTest(BaseAuthenticatedTestCase):
    """
    Testes do constraint XOR entre account e invoice em Transaction.
    Garante que nunca os dois estejam preenchidos ao mesmo tempo.
    """

    def setUp(self):
        super().setUp()
        from backend.api.categories.models import Category
        self.account = Account.objects.create(
            user=self.user,
            relative=self.relative,
            bank_name='Banco Teste',
            name='Conta Teste',
            account_type='corrente',
            color='#FF0000',
            balance='1000.00',
        )
        self.category = Category.objects.create(
            user=self.user,
            relative=self.relative,
            name='Alimentação',
            color='#FF5733',
            icon='food',
            type_category='despesas',
        )
        self.card = make_credit_card(self.user, self.relative)
        self.invoice = make_invoice(self.card, 3, 2026)

    def test_account_e_invoice_simultaneos_levanta_erro(self):
        """Preencher account E invoice ao mesmo tempo deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            Transaction.objects.create(
                user=self.user,
                relative=self.relative,
                account=self.account,
                invoice=self.invoice,
                category=self.category,
                type='despesa',
                amount='100.00',
                description='Teste XOR',
                date=datetime.date(2026, 3, 5),
                is_paid=False,
            )

    def test_apenas_account_permitido(self):
        """Transaction com apenas account (sem invoice) deve ser válida."""
        t = Transaction.objects.create(
            user=self.user,
            relative=self.relative,
            account=self.account,
            category=self.category,
            type='despesa',
            amount='100.00',
            description='Compra na conta',
            date=datetime.date(2026, 3, 5),
            is_paid=False,
        )
        self.assertIsNotNone(t.pk)

    def test_apenas_invoice_permitido(self):
        """Transaction com apenas invoice (sem account) deve ser válida."""
        t = Transaction.objects.create(
            user=self.user,
            relative=self.relative,
            invoice=self.invoice,
            category=self.category,
            type='despesa',
            amount='100.00',
            description='Compra no cartão',
            date=datetime.date(2026, 3, 5),
            is_paid=False,
        )
        self.assertIsNotNone(t.pk)


# ===========================================================================
# TESTES DE API — Invoice pay (Parte 7)
# ===========================================================================

class InvoicePayAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração para o endpoint POST /invoices/{id}/pay/.
    Cobre pagamento de fatura, débito de saldo e validações de negócio.
    """

    def setUp(self):
        super().setUp()
        self.card = make_credit_card(self.user, self.relative, closing_day=10, due_day=15)
        # Fatura fechada com total de R$ 350,00
        self.invoice = make_invoice(
            self.card, 1, 2026, status='fechada', total_amount=Decimal('350.00')
        )
        # Conta bancária com saldo suficiente para o pagamento
        self.account = Account.objects.create(
            user=self.user,
            relative=self.relative,
            bank_name='Banco Teste',
            name='Conta Corrente',
            account_type='corrente',
            color='#0000FF',
            balance=Decimal('1000.00'),
        )

    def _pay_url(self, invoice_pk):
        return reverse('invoice-pay', args=[invoice_pk])

    # --- Pagamento com sucesso ---

    def test_pay_retorna_200(self):
        """POST /invoices/{id}/pay/ com conta válida deve retornar 200."""
        response = self.client.post(self._pay_url(self.invoice.pk), {'account': self.account.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pay_atualiza_status_para_paga(self):
        """Após pagamento, o status da fatura deve ser 'paga'."""
        self.client.post(self._pay_url(self.invoice.pk), {'account': self.account.pk})
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'paga')

    def test_pay_define_paid_at(self):
        """Após pagamento, paid_at deve estar preenchido."""
        self.client.post(self._pay_url(self.invoice.pk), {'account': self.account.pk})
        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.paid_at)

    def test_pay_define_paid_via_account(self):
        """Após pagamento, paid_via_account deve apontar para a conta usada."""
        self.client.post(self._pay_url(self.invoice.pk), {'account': self.account.pk})
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_via_account, self.account)

    def test_pay_debita_saldo_da_conta(self):
        """Pagamento deve debitar total_amount do saldo da conta."""
        self.client.post(self._pay_url(self.invoice.pk), {'account': self.account.pk})
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal('650.00'))  # 1000 - 350

    def test_pay_retorna_campos_da_fatura(self):
        """Resposta do pagamento deve incluir campos atualizados da fatura."""
        response = self.client.post(self._pay_url(self.invoice.pk), {'account': self.account.pk})
        self.assertEqual(response.data['status'], 'paga')
        self.assertIsNotNone(response.data['paid_at'])
        self.assertEqual(response.data['paid_via_account'], self.account.pk)

    def test_pay_fatura_aberta_retorna_200(self):
        """Fatura com status 'aberta' também pode ser paga diretamente."""
        invoice_aberta = make_invoice(
            self.card, 2, 2026, status='aberta', total_amount=Decimal('100.00')
        )
        response = self.client.post(
            self._pay_url(invoice_aberta.pk), {'account': self.account.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice_aberta.refresh_from_db()
        self.assertEqual(invoice_aberta.status, 'paga')

    # --- Validações ---

    def test_pay_fatura_ja_paga_retorna_400(self):
        """POST em fatura já paga deve retornar 400."""
        invoice_paga = make_invoice(
            self.card, 3, 2026, status='paga', total_amount=Decimal('200.00')
        )
        response = self.client.post(
            self._pay_url(invoice_paga.pk), {'account': self.account.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('paga', str(response.data).lower())

    def test_pay_sem_account_retorna_400(self):
        """POST sem campo 'account' deve retornar 400."""
        response = self.client.post(self._pay_url(self.invoice.pk), {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('account', str(response.data).lower())

    def test_pay_conta_de_outro_usuario_retorna_400(self):
        """POST com conta de outro usuário deve retornar 400."""
        outro_user = self.create_additional_user('2')
        outro_relative = outro_user.relatives.first()
        conta_alheia = Account.objects.create(
            user=outro_user,
            relative=outro_relative,
            bank_name='Banco Alheio',
            name='Conta Alheia',
            account_type='corrente',
            color='#FF0000',
            balance=Decimal('500.00'),
        )
        response = self.client.post(
            self._pay_url(self.invoice.pk), {'account': conta_alheia.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('conta', str(response.data).lower())

    def test_pay_conta_inexistente_retorna_400(self):
        """POST com account_id inexistente deve retornar 400."""
        response = self.client.post(self._pay_url(self.invoice.pk), {'account': 999999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pay_fatura_de_outro_usuario_retorna_404(self):
        """POST em fatura de outro usuário deve retornar 404."""
        outro_user = self.create_additional_user('2')
        outro_relative = outro_user.relatives.first()
        outro_card = make_credit_card(outro_user, outro_relative)
        invoice_alheia = make_invoice(outro_card, 3, 2026, status='fechada', total_amount=Decimal('100.00'))
        response = self.client.post(
            self._pay_url(invoice_alheia.pk), {'account': self.account.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_pay_sem_autenticacao_retorna_401(self):
        """POST sem autenticação deve retornar 401."""
        self.unauthenticate()
        response = self.client.post(self._pay_url(self.invoice.pk), {'account': self.account.pk})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
