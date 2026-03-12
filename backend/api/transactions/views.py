import uuid
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
from .serializers import (
    RecurringRuleListSerializer,
    RecurringRuleSerializer,
    TransactionListSerializer,
    TransactionSerializer,
)


# ---------------------------------------------------------------------------
# Helpers de saldo
# ---------------------------------------------------------------------------

def _balance_delta(transaction_type: str, amount: Decimal) -> Decimal:
    """
    Retorna o delta de saldo para uma transação paga.
    Receita adiciona ao saldo; despesa subtrai.
    Transferência retorna zero — direção tratada por transfer_direction.
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


# ---------------------------------------------------------------------------
# Helpers de transferência
# ---------------------------------------------------------------------------

def _create_transfer_pair(origin: Transaction, destination_account: Account) -> None:
    """
    Cria o par de transações de transferência atomicamente.
    - Define transfer_pair_id e transfer_direction='debit' na transação de origem.
    - Cria a transação espelho na conta de destino com transfer_direction='credit'.
    - Aplica saldo se is_paid=True: débito na origem, crédito no destino.
    Deve ser chamado dentro de um bloco db_transaction.atomic().
    """
    pair_id = uuid.uuid4()

    # Marca a transação de origem como débito e associa o par
    Transaction.objects.filter(pk=origin.pk).update(
        transfer_pair_id=pair_id,
        transfer_direction='debit',
    )

    # Cria a transação espelho como crédito no destino
    Transaction.objects.create(
        user=origin.user,
        relative=origin.relative,
        account=destination_account,
        category=origin.category,
        recurring_rule=origin.recurring_rule,
        transfer_pair_id=pair_id,
        transfer_direction='credit',
        type='transferencia',
        amount=origin.amount,
        description=origin.description,
        notes=origin.notes,
        date=origin.date,
        is_paid=origin.is_paid,
    )

    # Atualiza saldo se a transferência já está confirmada
    if origin.is_paid:
        _apply_balance(origin.account_id, -origin.amount)  # débito na origem
        _apply_balance(destination_account.pk, origin.amount)  # crédito no destino


def _get_transfer_pair(instance: Transaction) -> Optional[Transaction]:
    """
    Retorna a transação par da transferência, ou None se não existir.
    """
    if not instance.transfer_pair_id:
        return None
    return Transaction.objects.filter(
        transfer_pair_id=instance.transfer_pair_id
    ).exclude(pk=instance.pk).first()


def _reverse_transfer_balance(debit_leg: Transaction, credit_leg: Transaction) -> None:
    """
    Reverte os saldos de ambas as pernas de uma transferência.
    Crédita a conta de origem (debit_leg) e debita a conta de destino (credit_leg).
    """
    if debit_leg.is_paid:
        _apply_balance(debit_leg.account_id, debit_leg.amount)   # credita origem
        _apply_balance(credit_leg.account_id, -credit_leg.amount)  # debita destino


def _apply_transfer_balance(debit_leg: Transaction, credit_leg: Transaction) -> None:
    """
    Aplica os saldos de ambas as pernas de uma transferência.
    Debita a conta de origem (debit_leg) e credita a conta de destino (credit_leg).
    """
    if debit_leg.is_paid:
        _apply_balance(debit_leg.account_id, -debit_leg.amount)  # débita origem
        _apply_balance(credit_leg.account_id, credit_leg.amount)  # credita destino


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
    Parte 3: criação de par de transferência, sincronização e delete do par.
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
                relative = Relative.objects.get(id=relative_id, user=self.request.user)
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
        Cria a transação e aplica a lógica de saldo conforme o tipo:
        - receita/despesa: atualiza o saldo da conta se is_paid=True
        - transferencia: cria o par (debit + credit) e aplica saldo em ambas as contas

        destination_account é um campo write-only do serializer, extraído antes do save()
        para que não seja passado ao model (que não possui esse campo).
        """
        with db_transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Extrai destination_account antes de salvar (não é campo do modelo)
            destination_account = serializer.validated_data.pop('destination_account', None)
            instance = serializer.save()

            if instance.type == 'transferencia' and destination_account:
                _create_transfer_pair(instance, destination_account)
            elif instance.is_paid and instance.account_id and instance.type in ('receita', 'despesa'):
                delta = _balance_delta(instance.type, instance.amount)
                _apply_balance(instance.account_id, delta)

            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        """
        Atualiza a transação e recalcula o impacto no saldo.

        Para transferências:
        - Bloqueia mudança de account (alteraria a direção do fluxo de forma ambígua)
        - Sincroniza amount, date, description, is_paid e notes com a transação par
        - Recalcula saldo de ambas as contas atomicamente

        Para receita/despesa:
        - Calcula delta líquido (old → new) considerando tipo, valor e conta
        - Trata mudança de conta separadamente

        Bloqueios:
        - transfer_pair_id não pode ser alterado diretamente
        - account não pode ser alterado em transferências existentes
        """
        if 'transfer_pair_id' in request.data:
            raise ValidationError({'transfer_pair_id': 'Este campo não pode ser alterado diretamente.'})

        with db_transaction.atomic():
            old = self.get_object()

            if old.transfer_pair_id:
                return self._update_transfer(request, old, *args, **kwargs)

            # --- lógica de receita/despesa ---
            old_account_id = old.account_id
            old_delta = Decimal('0')
            if old.is_paid and old_account_id and old.type in ('receita', 'despesa'):
                old_delta = _balance_delta(old.type, old.amount)

            response = super().update(request, *args, **kwargs)

            new = Transaction.objects.only(
                'is_paid', 'account_id', 'type', 'amount'
            ).get(pk=old.pk)
            new_account_id = new.account_id
            new_delta = Decimal('0')
            if new.is_paid and new_account_id and new.type in ('receita', 'despesa'):
                new_delta = _balance_delta(new.type, new.amount)

            if old_account_id != new_account_id:
                _apply_balance(old_account_id, -old_delta)
                _apply_balance(new_account_id, new_delta)
            else:
                net = new_delta - old_delta
                _apply_balance(new_account_id, net)

        return response

    def _update_transfer(self, request, old: Transaction, *args, **kwargs):
        """
        Atualiza uma transferência e seu par atomicamente.

        Campos sincronizados com o par: amount, date, description, is_paid, notes.
        Mudança de account é bloqueada — criaria ambiguidade na direção do fluxo.
        """
        if 'account' in request.data:
            raise ValidationError({
                'account': 'Não é possível alterar a conta de uma transferência. '
                           'Delete e recrie a transferência com as contas corretas.'
            })

        # Identifica as pernas de débito e crédito antes da atualização
        pair = _get_transfer_pair(old)
        debit_before = old if old.transfer_direction == 'debit' else pair
        credit_before = pair if old.transfer_direction == 'debit' else old

        old_is_paid = old.is_paid
        old_amount = old.amount

        # Atualiza a transação principal via super()
        response = super().update(request, *args, **kwargs)

        # Recarrega o estado atualizado
        new = Transaction.objects.only(
            'is_paid', 'amount', 'date', 'description', 'notes', 'category_id'
        ).get(pk=old.pk)

        # Sincroniza campos relevantes com a transação par
        sync_fields: dict = {}
        for field in ('amount', 'date', 'description', 'is_paid', 'notes'):
            if field in request.data:
                sync_fields[field] = getattr(new, field)
        if 'category' in request.data:
            sync_fields['category_id'] = new.category_id
        if sync_fields and pair:
            Transaction.objects.filter(pk=pair.pk).update(**sync_fields)

        # Recalcula o saldo: reverte estado antigo e aplica novo
        new_amount = new.amount
        new_is_paid = new.is_paid

        if debit_before and credit_before:
            # Reverte o estado anterior (usando o amount/is_paid de antes do update)
            if old_is_paid:
                _apply_balance(debit_before.account_id, old_amount)    # credita origem
                _apply_balance(credit_before.account_id, -old_amount)  # debita destino

            # Aplica o novo estado
            if new_is_paid:
                _apply_balance(debit_before.account_id, -new_amount)   # débita origem
                _apply_balance(credit_before.account_id, new_amount)   # credita destino

        return response

    def destroy(self, request, *args, **kwargs):
        """
        Deleta a transação. Para transferências, deleta o par atomicamente e
        reverte o saldo de ambas as contas. Para receita/despesa, reverte o
        saldo da conta vinculada se is_paid=True.
        """
        with db_transaction.atomic():
            instance = self.get_object()

            if instance.transfer_pair_id:
                # Localiza ambas as pernas antes de deletar
                pair_qs = Transaction.objects.filter(
                    transfer_pair_id=instance.transfer_pair_id
                )
                debit_leg = pair_qs.filter(transfer_direction='debit').first()
                credit_leg = pair_qs.filter(transfer_direction='credit').first()

                if debit_leg and credit_leg:
                    _reverse_transfer_balance(debit_leg, credit_leg)

                pair_qs.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)

            # Receita/despesa: reverte saldo se estava pago
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
                relative = Relative.objects.get(id=relative_id, user=self.request.user)
                queryset = queryset.filter(relative=relative)
            except Relative.DoesNotExist:
                raise ValidationError({
                    'X-Relative-Id': f'Perfil com ID {relative_id} não encontrado ou não pertence ao usuário.'
                })

        if self.action == 'list':
            # Permite listar regras inativas com ?only_inactive=true
            only_inactive = self.request.query_params.get('only_inactive', 'false')
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
