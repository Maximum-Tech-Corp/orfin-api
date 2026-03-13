import datetime
from decimal import Decimal

from django.urls import reverse
from rest_framework import status

from backend.api.accounts.models import Account
from backend.api.categories.models import Category
from backend.api.credit_cards.models import CreditCard, Invoice
from backend.api.transactions.models import Transaction

from .base import BaseAuthenticatedTestCase


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------


def make_account(user, relative, name='Conta', balance=Decimal('0'), include_calc=True, is_archived=False):
    """Cria uma conta mínima para uso nos testes."""
    return Account.objects.create(
        user=user,
        relative=relative,
        bank_name='Banco Teste',
        name=name,
        account_type='corrente',
        color='#FF0000',
        balance=balance,
        include_calc=include_calc,
        is_archived=is_archived,
    )


def make_category(user, relative, name, type_category='despesas'):
    """Cria uma categoria mínima para uso nos testes."""
    return Category.objects.create(
        user=user,
        relative=relative,
        name=name,
        color='#FF5733',
        icon='food',
        type_category=type_category,
    )


def make_transaction(
    user, relative, account, category,
    type='despesa',
    amount='100.00',
    date=datetime.date(2026, 3, 15),
    is_paid=True,
    invoice=None,
):
    """Cria uma transação mínima para uso nos testes."""
    return Transaction.objects.create(
        user=user,
        relative=relative,
        account=account if not invoice else None,
        invoice=invoice,
        category=category,
        type=type,
        amount=amount,
        description='Transação Teste',
        date=date,
        is_paid=is_paid,
    )


# ===========================================================================
# TESTES DE API — Dashboard
# ===========================================================================


class DashboardAPITest(BaseAuthenticatedTestCase):
    """
    Testes de integração para GET /api/v1/dashboard/.
    Cobre agregações de saldo, receitas, despesas, saldo do mês e breakdown por categoria.
    """

    def setUp(self):
        super().setUp()
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(self.relative.id)
        self.url = reverse('dashboard')

        # Contas do perfil
        self.account = make_account(
            self.user, self.relative, name='Conta Principal', balance=Decimal('3000.00')
        )
        self.account_invest = make_account(
            self.user, self.relative, name='Investimentos', balance=Decimal('2000.00')
        )

        # Categorias
        self.cat_alimentacao = make_category(self.user, self.relative, 'Alimentação')
        self.cat_transporte = make_category(self.user, self.relative, 'Transporte')
        self.cat_salario = make_category(
            self.user, self.relative, 'Salário', type_category='receitas'
        )

    def _get(self, month=3, year=2026, **kwargs):
        params = {'month': month, 'year': year}
        params.update(kwargs)
        return self.client.get(self.url, params)

    # --- Estrutura da resposta ---

    def test_dashboard_retorna_200(self):
        """GET /dashboard/ com parâmetros válidos deve retornar 200."""
        response = self._get()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_dashboard_retorna_campos_esperados(self):
        """Resposta deve conter todos os campos do contrato."""
        response = self._get()
        campos = ['balance_total', 'receitas_mes', 'despesas_mes', 'saldo_mes', 'por_categoria']
        for campo in campos:
            self.assertIn(campo, response.data)

    # --- balance_total ---

    def test_balance_total_soma_contas_include_calc(self):
        """balance_total deve somar saldos das contas com include_calc=True."""
        # Conta Principal (3000) + Investimentos (2000) = 5000
        response = self._get()
        self.assertEqual(response.data['balance_total'], '5000.00')

    def test_balance_total_exclui_contas_sem_include_calc(self):
        """balance_total não deve incluir contas com include_calc=False."""
        make_account(
            self.user, self.relative, 'Poupança Excluída',
            balance=Decimal('999.00'), include_calc=False
        )
        response = self._get()
        self.assertEqual(response.data['balance_total'], '5000.00')

    def test_balance_total_exclui_contas_arquivadas(self):
        """balance_total não deve incluir contas arquivadas."""
        make_account(
            self.user, self.relative, 'Conta Arquivada',
            balance=Decimal('500.00'), is_archived=True
        )
        response = self._get()
        self.assertEqual(response.data['balance_total'], '5000.00')

    def test_balance_total_sem_contas_retorna_zero(self):
        """Sem contas elegíveis, balance_total deve ser 0."""
        # Cria um segundo usuário/relative sem contas
        outro_user = self.create_additional_user('2')
        outro_relative = outro_user.relatives.first()
        self.client.defaults['HTTP_X_RELATIVE_ID'] = str(outro_relative.id)
        self.authenticate_user(outro_user)
        response = self._get()
        self.assertEqual(response.data['balance_total'], '0')

    def test_balance_total_nao_inclui_contas_de_outro_perfil(self):
        """balance_total não deve misturar contas de perfis diferentes do mesmo usuário."""
        from backend.api.relatives.models import Relative
        outro_relative = Relative.objects.create(
            name='Trabalho', image_num=2, user=self.user
        )
        make_account(
            self.user, outro_relative, 'Conta Trabalho',
            balance=Decimal('9999.00')
        )
        response = self._get()
        # Apenas as contas do self.relative (3000 + 2000 = 5000)
        self.assertEqual(response.data['balance_total'], '5000.00')

    # --- receitas_mes e despesas_mes ---

    def test_receitas_mes_soma_apenas_pagas(self):
        """receitas_mes deve somar apenas transações pagas (is_paid=True)."""
        make_transaction(
            self.user, self.relative, self.account, self.cat_salario,
            type='receita', amount='5000.00', is_paid=True
        )
        make_transaction(
            self.user, self.relative, self.account, self.cat_salario,
            type='receita', amount='1000.00', is_paid=False  # não paga — não entra
        )
        response = self._get()
        self.assertEqual(response.data['receitas_mes'], '5000.00')

    def test_despesas_mes_soma_apenas_pagas(self):
        """despesas_mes deve somar apenas transações pagas."""
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='350.00', is_paid=True
        )
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='200.00', is_paid=False  # não paga — não entra
        )
        response = self._get()
        self.assertEqual(response.data['despesas_mes'], '350.00')

    def test_saldo_mes_eh_receitas_menos_despesas(self):
        """saldo_mes deve ser receitas_mes - despesas_mes."""
        make_transaction(
            self.user, self.relative, self.account, self.cat_salario,
            type='receita', amount='5000.00', is_paid=True
        )
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='1200.00', is_paid=True
        )
        response = self._get()
        self.assertEqual(response.data['receitas_mes'], '5000.00')
        self.assertEqual(response.data['despesas_mes'], '1200.00')
        self.assertEqual(response.data['saldo_mes'], '3800.00')

    def test_saldo_mes_negativo_quando_despesas_superam_receitas(self):
        """saldo_mes pode ser negativo."""
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='2000.00', is_paid=True
        )
        response = self._get()
        self.assertEqual(response.data['saldo_mes'], '-2000.00')

    def test_receitas_despesas_zeradas_quando_nao_ha_transacoes(self):
        """Sem transações no mês, receitas e despesas devem ser 0."""
        response = self._get()
        self.assertEqual(response.data['receitas_mes'], '0')
        self.assertEqual(response.data['despesas_mes'], '0')
        self.assertEqual(response.data['saldo_mes'], '0')

    def test_filtra_pelo_mes_correto(self):
        """Transações de outros meses não devem ser incluídas."""
        # Transação em março — deve ser incluída
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='500.00', date=datetime.date(2026, 3, 15), is_paid=True
        )
        # Transação em abril — não deve ser incluída
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='999.00', date=datetime.date(2026, 4, 1), is_paid=True
        )
        response = self._get(month=3, year=2026)
        self.assertEqual(response.data['despesas_mes'], '500.00')

    def test_nao_inclui_transferencias_em_receitas_despesas(self):
        """Transferências não devem entrar em receitas_mes nem despesas_mes."""
        make_transaction(
            self.user, self.relative, self.account, None,
            type='transferencia', amount='1000.00', is_paid=True
        )
        response = self._get()
        self.assertEqual(response.data['receitas_mes'], '0')
        self.assertEqual(response.data['despesas_mes'], '0')

    # --- por_categoria ---

    def test_por_categoria_inclui_transacoes_nao_pagas(self):
        """por_categoria usa competência — inclui transações não pagas."""
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='300.00', is_paid=True
        )
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='150.00', is_paid=False
        )
        response = self._get()
        categorias = {c['category_name']: c for c in response.data['por_categoria']}
        # Deve somar as duas: 300 + 150 = 450
        self.assertEqual(categorias['Alimentação']['total'], '450.00')

    def test_por_categoria_inclui_transacoes_de_cartao(self):
        """por_categoria inclui transações de cartão (is_paid=False por natureza)."""
        card = CreditCard.objects.create(
            user=self.user,
            relative=self.relative,
            name='Nubank',
            color='#8A05BE',
            limit=Decimal('5000.00'),
            closing_day=10,
            due_day=15,
        )
        invoice = Invoice.objects.create(
            credit_card=card,
            reference_month=3,
            reference_year=2026,
            status='aberta',
            due_date=datetime.date(2026, 3, 15),
            total_amount=Decimal('0'),
        )
        make_transaction(
            self.user, self.relative, None, self.cat_alimentacao,
            type='despesa', amount='250.00', is_paid=False, invoice=invoice
        )
        response = self._get()
        categorias = {c['category_name']: c for c in response.data['por_categoria']}
        self.assertIn('Alimentação', categorias)
        self.assertEqual(categorias['Alimentação']['total'], '250.00')

    def test_por_categoria_agrupa_por_categoria(self):
        """Transações da mesma categoria devem ser somadas em um único item."""
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='100.00', is_paid=True
        )
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='200.00', is_paid=True
        )
        response = self._get()
        categorias = {c['category_name']: c for c in response.data['por_categoria']}
        self.assertEqual(categorias['Alimentação']['total'], '300.00')

    def test_por_categoria_retorna_campos_corretos(self):
        """Cada item de por_categoria deve ter todos os campos esperados."""
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='100.00', is_paid=True
        )
        response = self._get()
        item = response.data['por_categoria'][0]
        for campo in ['category_id', 'category_name', 'category_color', 'category_icon', 'type_category', 'total']:
            self.assertIn(campo, item)

    def test_por_categoria_vazio_sem_transacoes(self):
        """por_categoria deve ser lista vazia quando não há transações no mês."""
        response = self._get()
        self.assertEqual(response.data['por_categoria'], [])

    def test_por_categoria_multiplas_categorias(self):
        """por_categoria deve listar cada categoria separadamente."""
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='300.00', is_paid=True
        )
        make_transaction(
            self.user, self.relative, self.account, self.cat_transporte,
            type='despesa', amount='100.00', is_paid=True
        )
        make_transaction(
            self.user, self.relative, self.account, self.cat_salario,
            type='receita', amount='5000.00', is_paid=True
        )
        response = self._get()
        self.assertEqual(len(response.data['por_categoria']), 3)

    def test_por_categoria_nao_inclui_transferencias(self):
        """Transferências não devem aparecer em por_categoria."""
        make_transaction(
            self.user, self.relative, self.account, None,
            type='transferencia', amount='1000.00', is_paid=True
        )
        response = self._get()
        self.assertEqual(response.data['por_categoria'], [])

    # --- Parâmetros ---

    def test_sem_month_year_usa_mes_atual(self):
        """Sem query params, o endpoint usa o mês e ano correntes."""
        today = datetime.date.today()
        make_transaction(
            self.user, self.relative, self.account, self.cat_alimentacao,
            type='despesa', amount='100.00',
            date=today, is_paid=True
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['despesas_mes'], '100.00')

    def test_month_invalido_retorna_400(self):
        """month=13 deve retornar 400."""
        response = self._get(month=13)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('month', str(response.data).lower())

    def test_month_nao_numerico_retorna_400(self):
        """month=abc deve retornar 400."""
        response = self.client.get(self.url, {'month': 'abc', 'year': 2026})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Header X-Relative-Id ---

    def test_sem_relative_header_retorna_400(self):
        """GET sem X-Relative-Id deve retornar 400."""
        del self.client.defaults['HTTP_X_RELATIVE_ID']
        response = self._get()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('x-relative-id', str(response.data).lower())

    def test_relative_id_invalido_retorna_400(self):
        """GET com X-Relative-Id inexistente deve retornar 400."""
        self.client.defaults['HTTP_X_RELATIVE_ID'] = '999999'
        response = self._get()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nao_inclui_dados_de_outro_usuario(self):
        """Dashboard não deve misturar dados de outros usuários."""
        outro_user = self.create_additional_user('2')
        outro_relative = outro_user.relatives.first()
        outro_account = make_account(outro_user, outro_relative, balance=Decimal('9999.00'))
        cat_outro = make_category(outro_user, outro_relative, 'CatOutro')
        make_transaction(
            outro_user, outro_relative, outro_account, cat_outro,
            type='despesa', amount='9999.00', is_paid=True
        )
        response = self._get()
        self.assertEqual(response.data['despesas_mes'], '0')

    # --- Autenticação ---

    def test_sem_autenticacao_retorna_401(self):
        """GET sem autenticação deve retornar 401."""
        self.unauthenticate()
        response = self._get()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
