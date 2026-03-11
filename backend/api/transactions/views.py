from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from backend.api.relatives.models import Relative

from .models import RecurringRule, Transaction
from .serializers import (
    RecurringRuleListSerializer,
    RecurringRuleSerializer,
    TransactionListSerializer,
    TransactionSerializer,
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

    Nota: lógica de atualização de saldo (Parte 2) e transferências (Parte 3)
    serão implementadas nas próximas etapas.
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
        Na listagem, exclui transações arquivadas e aplica filtros opcionais de período e tipo.
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
            queryset = queryset.filter(is_archived=False)

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

    def update(self, request, *args, **kwargs):
        """
        Impede alteração direta dos campos de controle de par de transferência.
        Nota: a lógica de reversão/aplicação de saldo será adicionada na Parte 2.
        """
        if 'transfer_pair_id' in request.data:
            raise ValidationError({'transfer_pair_id': 'Este campo não pode ser alterado diretamente.'})
        return super().update(request, *args, **kwargs)


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
