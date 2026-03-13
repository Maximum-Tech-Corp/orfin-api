import datetime
from decimal import Decimal

from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from backend.api.accounts.models import Account
from backend.api.relatives.models import Relative
from backend.api.transactions.models import Transaction


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """
    Retorna o resumo financeiro do mês para o perfil selecionado.
    GET /api/v1/dashboard/?month=3&year=2026

    Header obrigatório: X-Relative-Id

    Paradigmas aplicados:
    - Caixa (is_paid=True): balance_total, receitas_mes, despesas_mes, saldo_mes
    - Competência (todas as transações do mês): por_categoria

    Resposta:
    {
        "balance_total":  "5000.00",   — soma dos saldos das contas ativas (include_calc=True)
        "receitas_mes":   "2000.00",   — receitas pagas no mês
        "despesas_mes":   "1500.00",   — despesas pagas no mês
        "saldo_mes":      "500.00",    — receitas_mes - despesas_mes
        "por_categoria":  [...]        — total por categoria (inclui transações não pagas)
    }
    """
    user = request.user
    today = datetime.date.today()

    # Resolve o perfil via header X-Relative-Id
    relative_id = request.headers.get('X-Relative-Id')
    if not relative_id:
        raise ValidationError({'X-Relative-Id': 'Header X-Relative-Id é obrigatório.'})

    try:
        relative = Relative.objects.get(id=relative_id, user=user)
    except Relative.DoesNotExist:
        raise ValidationError({
            'X-Relative-Id': (
                f'Perfil com ID {relative_id} não encontrado '
                'ou não pertence ao usuário.'
            )
        })

    # Parâmetros de período — padrão: mês e ano correntes
    try:
        month = int(request.query_params.get('month', today.month))
        year = int(request.query_params.get('year', today.year))
    except (ValueError, TypeError):
        raise ValidationError(
            {'detail': 'Parâmetros month e year devem ser inteiros válidos.'}
        )

    if not (1 <= month <= 12):
        raise ValidationError({'month': 'O mês deve estar entre 1 e 12.'})

    # ---------------------------------------------------------------------------
    # Saldo total das contas (paradigma caixa)
    # ---------------------------------------------------------------------------
    # Soma apenas contas ativas com include_calc=True do perfil selecionado
    balance_total = (
        Account.objects.filter(
            user=user,
            relative=relative,
            include_calc=True,
            is_archived=False,
        ).aggregate(total=Sum('balance'))['total']
    ) or Decimal('0')

    # ---------------------------------------------------------------------------
    # Receitas e despesas pagas no mês (paradigma caixa — only is_paid=True)
    # ---------------------------------------------------------------------------
    paid_transactions = Transaction.objects.filter(
        user=user,
        relative=relative,
        date__month=month,
        date__year=year,
        is_paid=True,
    )

    receitas_mes = (
        paid_transactions.filter(type='receita')
        .aggregate(total=Sum('amount'))['total']
    ) or Decimal('0')

    despesas_mes = (
        paid_transactions.filter(type='despesa')
        .aggregate(total=Sum('amount'))['total']
    ) or Decimal('0')

    saldo_mes = receitas_mes - despesas_mes

    # ---------------------------------------------------------------------------
    # Breakdown por categoria (paradigma competência — todas as transações do mês)
    # ---------------------------------------------------------------------------
    # Inclui transações não pagas para mostrar quando a compra aconteceu.
    # Transações de cartão (is_paid=False) aparecem aqui mas não no saldo do mês.
    por_categoria_qs = (
        Transaction.objects.filter(
            user=user,
            relative=relative,
            date__month=month,
            date__year=year,
            type__in=('receita', 'despesa'),
            category__isnull=False,
        )
        .values(
            'category__id',
            'category__name',
            'category__color',
            'category__icon',
            'category__type_category',
        )
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    por_categoria = [
        {
            'category_id': str(item['category__id']),
            'category_name': item['category__name'],
            'category_color': item['category__color'],
            'category_icon': item['category__icon'],
            'type_category': item['category__type_category'],
            'total': str(item['total']),
        }
        for item in por_categoria_qs
    ]

    return Response({
        'balance_total': str(balance_total),
        'receitas_mes': str(receitas_mes),
        'despesas_mes': str(despesas_mes),
        'saldo_mes': str(saldo_mes),
        'por_categoria': por_categoria,
    })
