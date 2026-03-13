from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from backend.api.relatives.models import Relative

from .models import CreditCard, Invoice
from .serializers import CreditCardListSerializer, CreditCardSerializer, InvoiceSerializer


class CreditCardViewSet(viewsets.ModelViewSet):
    """
    ViewSet para operações CRUD da entidade CreditCard.

    Filtragem disponível via query params:
    - only_archived (bool): true = lista apenas arquivados; false (padrão) = apenas ativos

    Requer header X-Relative-Id para todas as operações.

    Parte 5: CRUD básico de cartões + listagem de faturas por cartão.
    """

    queryset = CreditCard.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Retorna serializer compacto para listagem e completo para demais ações.
        """
        if self.action == 'list':
            return CreditCardListSerializer
        return CreditCardSerializer

    def get_queryset(self):
        """
        Filtra cartões pelo usuário autenticado e pelo perfil (X-Relative-Id).
        Por padrão retorna apenas cartões ativos; ?only_archived=true retorna os arquivados.
        Para ações que precisam acessar qualquer cartão (unarchive, invoices, retrieve),
        o filtro de arquivamento não é aplicado.
        """
        queryset = CreditCard.objects.filter(user=self.request.user)

        # Filtro por perfil via header
        relative_id = self.request.headers.get('X-Relative-Id')
        if relative_id:
            try:
                relative = Relative.objects.get(
                    id=relative_id, user=self.request.user
                )
                queryset = queryset.filter(relative=relative)
            except Relative.DoesNotExist:
                raise ValidationError({
                    'X-Relative-Id': (
                        f'Perfil com ID {relative_id} não encontrado '
                        'ou não pertence ao usuário.'
                    )
                })

        # Filtro de arquivamento aplicado apenas na listagem padrão
        if self.action == 'list':
            only_archived = self.request.query_params.get('only_archived', 'false')
            if only_archived.lower() == 'true':
                queryset = queryset.filter(is_archived=True)
            else:
                queryset = queryset.filter(is_archived=False)

        return queryset

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete: arquiva o cartão ao invés de deletá-lo fisicamente.
        Preserva o histórico de faturas e transações vinculadas.
        """
        card = self.get_object()
        card.soft_delete()
        return Response(
            {'detail': 'Cartão arquivado com sucesso.'},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'], url_path='invoices')
    def invoices(self, request, pk=None):
        """
        Lista todas as faturas do cartão.
        Atualiza o status das faturas abertas de forma lazy antes de retornar.
        GET /api/v1/credit-cards/{id}/invoices/
        """
        card = self.get_object()

        invoices_qs = Invoice.objects.filter(
            credit_card=card
        ).select_related('credit_card')

        # Atualização lazy de status: fecha faturas cujo período já encerrou
        for inv in invoices_qs.filter(status='aberta'):
            inv.update_status()

        # Re-consulta após possíveis atualizações de status
        invoices_qs = Invoice.objects.filter(
            credit_card=card
        ).select_related('credit_card')

        serializer = InvoiceSerializer(invoices_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='unarchive')
    def unarchive(self, request, pk=None):
        """
        Desarquiva um cartão previamente arquivado.
        POST /api/v1/credit-cards/{id}/unarchive/
        """
        card = self.get_object()
        if not card.is_archived:
            raise ValidationError({'detail': 'Este cartão não está arquivado.'})
        card.is_archived = False
        card.save(update_fields=['is_archived', 'updated_at'])
        serializer = CreditCardSerializer(card, context={'request': request})
        return Response(serializer.data)


class InvoiceViewSet(
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet de leitura para Invoice.
    Expõe apenas GET detail — criação e atualização são feitas automaticamente
    pela lógica de transações de cartão (Parte 6).

    Acesso restrito ao dono do cartão: filtra por credit_card__user.
    """

    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Retorna apenas faturas cujo cartão pertence ao usuário autenticado.
        """
        return Invoice.objects.filter(
            credit_card__user=self.request.user
        ).select_related('credit_card', 'paid_via_account')

    def retrieve(self, request, *args, **kwargs):
        """
        Retorna o detalhe da fatura, atualizando o status de forma lazy antes da resposta.
        GET /api/v1/invoices/{id}/
        """
        instance = self.get_object()
        # Atualiza status lazy: fecha a fatura se o período já encerrou
        instance.update_status()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
