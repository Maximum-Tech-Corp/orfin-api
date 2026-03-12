from decimal import Decimal
from typing import Optional

from django.db import transaction as db_transaction
from django.db.models import F
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from backend.api.accounts.models import Account
from backend.api.relatives.models import Relative

from .models import RecurringRule, Transaction
from .serializers import (RecurringRuleListSerializer, RecurringRuleSerializer,
                          TransactionListSerializer, TransactionSerializer)

# ---------------------------------------------------------------------------
# Helpers de saldo
# ---------------------------------------------------------------------------


def _balance_delta(transaction_type: str, amount: Decimal) -> Decimal:
    """
    Retorna o delta de saldo para uma transação paga.
    Receita adiciona ao saldo; despesa subtrai.
    Transferência retorna zero — tratada separadamente na Parte 3.
    """
    if transaction_type == 'receita':
        return amount
    if transaction_type == 'despesa':
        return -amount
    return Decimal('0')


def _apply_balance(account_id: Optional[int], delta: Decimal) -> None:
    """
    Aplica um delta ao saldo da conta de forma atômica usando F().
    Recebe o account_id diretamente para evitar carregar o objeto Account em memória.
    Usar F() evita race conditions — nunca carrega o valor atual em memória.
    """
    if delta and account_id:
        Account.objects.filter(pk=account_id).update(
            balance=F('balance') + delta
        )


class TransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para operações CRUD da entidade Transaction.

    Filtragem disponível via query params:
    - month (int): mês de competência (1–12)
    - year (int): ano de competência
    - type (str): receita | despesa | transferencia
    - account (uuid): ID da conta
    - category (uuid): ID da categoria
    - is_paid (bool): true | false

    Requer header X-Relative-Id para todas as operações.

    Parte 2: lógica de atualização de saldo em create, update e destroy.
    Parte 3: transferências (transfer_pair_id) serão implementadas na próxima etapa.
    """

    queryset = Transaction.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Retorna serializer compacto para listagem e completo para demais ações.
        """
        if self.action == 'list':
            return TransactionListSerializer
        return TransactionSerializer

    def get_queryset(self):
        """
        Filtra transações pelo usuário autenticado e pelo perfil (X-Relative-Id).
        Na listagem, aplica filtros opcionais de período, tipo, conta, categoria e status.
        """
        queryset = Transaction.objects.filter(user=self.request.user)

        # Filtro obrigatório por perfil via header
        relative_id = self.request.headers.get('X-Relative-Id')
        if relative_id:
            try:
                relative = Relative.objects.get(
                    id=relative_id, user=self.request.user)
                queryset = queryset.filter(relative=relative)
            except Relative.DoesNotExist:
                raise ValidationError({
                    'X-Relative-Id': f'Perfil com ID {relative_id} não encontrado ou não pertence ao usuário.'
                })

        # Na listagem, aplica filtros adicionais de período e status
        if self.action == 'list':
            month = self.request.query_params.get('month')
            year = self.request.query_params.get('year')
            if month:
                queryset = queryset.filter(date__month=month)
            if year:
                queryset = queryset.filter(date__year=year)

            transaction_type = self.request.query_params.get('type')
            if transaction_type:
                queryset = queryset.filter(type=transaction_type)

            account_id = self.request.query_params.get('account')
            if account_id:
                queryset = queryset.filter(account_id=account_id)

            category_id = self.request.query_params.get('category')
            if category_id:
                queryset = queryset.filter(category_id=category_id)

            is_paid = self.request.query_params.get('is_paid')
            if is_paid is not None:
                queryset = queryset.filter(is_paid=is_paid.lower() == 'true')

        return queryset

    def create(self, request, *args, **kwargs):
        """
        Cria a transação e, se is_paid=True e houver conta vinculada,
        atualiza o saldo da conta atomicamente.
        Usa o padrão DRF de acesso direto ao serializer para obter a instância
        sem query extra e sem avisos de tipo (response.data pode ser None).
        Só afeta receitas e despesas — transferências serão tratadas na Parte 3.
        """
        with db_transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()

            if (
                instance.is_paid
                and instance.account_id
                and instance.type in ('receita', 'despesa')
            ):
                delta = _balance_delta(instance.type, instance.amount)
                _apply_balance(instance.account_id, delta)

            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        """
        Atualiza a transação e recalcula o impacto no saldo da conta.

        Cenários tratados:
        - Mudança de is_paid (false→true aplica, true→false reverte)
        - Mudança de amount (reverte antigo, aplica novo)
        - Mudança de type (reverte direção antiga, aplica nova)
        - Mudança de account (reverte da conta antiga, aplica na nova)
        - Qualquer combinação acima, de forma atômica

        Bloqueios:
        - transfer_pair_id não pode ser alterado diretamente
        - Transferências serão tratadas na Parte 3
        """
        if 'transfer_pair_id' in request.data:
            raise ValidationError(
                {'transfer_pair_id': 'Este campo não pode ser alterado diretamente.'})

        with db_transaction.atomic():
            # Captura o account_id e delta antigo antes de qualquer alteração
            old = self.get_object()
            old_account_id = old.account_id
            old_delta = Decimal('0')
            if old.is_paid and old_account_id and old.type in ('receita', 'despesa'):
                old_delta = _balance_delta(old.type, old.amount)

            response = super().update(request, *args, **kwargs)

            # Recarrega apenas os campos necessários para calcular o novo delta
            new = Transaction.objects.only(
                'is_paid', 'account_id', 'type', 'amount'
            ).get(pk=old.pk)
            new_account_id = new.account_id
            new_delta = Decimal('0')
            if new.is_paid and new_account_id and new.type in ('receita', 'despesa'):
                new_delta = _balance_delta(new.type, new.amount)

            if old_account_id != new_account_id:
                # Conta mudou: reverte da conta antiga e aplica na nova separadamente
                _apply_balance(old_account_id, -old_delta)
                _apply_balance(new_account_id, new_delta)
            else:
                # Mesma conta (ou ambas nulas): aplica apenas o delta líquido
                net = new_delta - old_delta
                _apply_balance(new_account_id, net)

        return response

    def destroy(self, request, *args, **kwargs):
        """
        Hard delete da transação. Se estava paga e vinculada a uma conta,
        reverte o delta no saldo antes de deletar.
        Transferências (Parte 3) exigirão lógica adicional de par.
        """
        with db_transaction.atomic():
            instance = self.get_object()
            if (
                instance.is_paid
                and instance.account_id
                and instance.type in ('receita', 'despesa')
            ):
                delta = _balance_delta(instance.type, instance.amount)
                _apply_balance(instance.account_id, -delta)
            return super().destroy(request, *args, **kwargs)


class RecurringRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet para operações CRUD da entidade RecurringRule.

    Requer header X-Relative-Id para todas as operações.

    Nota: lógica de geração de instâncias de Transaction (Parte 4)
    será implementada na próxima etapa correspondente.
    """

    queryset = RecurringRule.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Retorna serializer compacto para listagem e completo para demais ações.
        """
        if self.action == 'list':
            return RecurringRuleListSerializer
        return RecurringRuleSerializer

    def get_queryset(self):
        """
        Filtra regras pelo usuário autenticado e pelo perfil (X-Relative-Id).
        Por padrão, lista apenas regras ativas.
        """
        queryset = RecurringRule.objects.filter(user=self.request.user)

        # Filtro por perfil via header
        relative_id = self.request.headers.get('X-Relative-Id')
        if relative_id:
            try:
                relative = Relative.objects.get(
                    id=relative_id, user=self.request.user)
                queryset = queryset.filter(relative=relative)
            except Relative.DoesNotExist:
                raise ValidationError({
                    'X-Relative-Id': f'Perfil com ID {relative_id} não encontrado ou não pertence ao usuário.'
                })

        if self.action == 'list':
            # Permite listar regras inativas com ?only_inactive=true
            only_inactive = self.request.query_params.get(
                'only_inactive', 'false')
            if only_inactive.lower() == 'true':
                queryset = queryset.filter(is_active=False)
            else:
                queryset = queryset.filter(is_active=True)

        return queryset

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete: desativa a regra ao invés de deletá-la.
        Nota: lógica de arquivamento de instâncias futuras será implementada na Parte 4.
        """
        rule = self.get_object()
        rule.soft_delete()

        return Response(
            {'detail': 'Regra de recorrência desativada com sucesso.'},
            status=status.HTTP_200_OK
        )
