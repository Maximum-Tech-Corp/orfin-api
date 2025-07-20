from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Account
from .serializers import AccountSerializer


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def get_queryset(self):
        """
        Filtros do GET:
        Por padrão, mostra todas as contas ativas
        """
        queryset = Account.objects.all()

        # Se houver parâmetro 'only_archived'=true, retorna somente as contas arquivadas
        only_archived = self.request.GET.get('only_archived', 'false')
        if only_archived.lower() == 'true':
            queryset = queryset.filter(is_archived=True)
        else:
            queryset = queryset.filter(is_archived=False)

        # Se houver parâmetro 'name', filtra por nome
        name = self.request.GET.get('name', None)
        if name:
            queryset = queryset.filter(name__icontains=name)

        return queryset.order_by('name')

    def destroy(self, request, *args, **kwargs):
        """
        Sobrescreve o método destroy para implementar soft delete.
        Arquiva a conta ao invés de deletá-la fisicamente.
        """
        try:
            # Arquiva a conta
            account = self.get_object()
            account.is_archived = True
            account.save()

            return Response(
                {"detail": "Conta arquivada com sucesso."},
                status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {"detail": "Conta não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

    def update(self, request, *args, **kwargs):
        if 'balance' in request.data:
            raise ValidationError(
                {'balance': 'Não é permitido alterar o saldo da conta.'})
        return super().update(request, *args, **kwargs)
