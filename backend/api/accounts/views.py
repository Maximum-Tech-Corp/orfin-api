from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from backend.api.relatives.models import Relative

from .models import Account
from .serializers import AccountSerializer


class AccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet para operações CRUD da entidade Account.
    Permite criar, listar, recuperar, atualizar e arquivar contas financeiras.
    """
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Filtros do GET:
        Mostra apenas contas do usuário autenticado
        Se X-Relative-Id no header, filtra por perfil específico
        Por padrão, mostra todas as contas ativas
        """
        queryset = Account.objects.filter(user=self.request.user)

        # Filtro por perfil se X-Relative-Id estiver presente no header
        relative_id = self.request.headers.get('X-Relative-Id')
        if relative_id:
            try:
                relative = Relative.objects.get(id=relative_id, user=self.request.user)
                queryset = queryset.filter(relative=relative)
            except Relative.DoesNotExist:
                # Se perfil não existir, retorna um erro
                raise ValidationError({
                    'X-Relative-Id': f'Perfil com ID {relative_id} não encontrado ou não pertence ao usuário. Por favor limpar os Cookies do Navegador.'
                })

        # Se houver parâmetro 'only_archived'=true, retorna somente as contas arquivadas
        only_archived = self.request.query_params.get('only_archived', 'false')
        if only_archived.lower() == 'true':
            queryset = queryset.filter(is_archived=True)
        else:
            queryset = queryset.filter(is_archived=False)

        # Se houver parâmetro 'name', filtra por nome
        name = self.request.query_params.get('name', None)
        if name:
            queryset = queryset.filter(name__icontains=name)

        return queryset.order_by('name')

    def perform_create(self, serializer):
        """
        Associa a conta ao usuário autenticado durante a criação.
        """
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """
        Sobrescreve o método destroy para implementar soft delete.
        Arquiva a conta ao invés de deletá-la fisicamente.
        """
        # get_object() já lida com 404 e permissões automaticamente
        account = self.get_object()
        account.is_archived = True
        account.save()

        return Response(
            {"detail": "Conta arquivada com sucesso."},
            status=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        if 'balance' in request.data:
            current_account = self.get_object()
            request_balance = Decimal(str(request.data['balance']))

            if current_account.balance != request_balance:
                raise ValidationError(
                    {'balance': 'Não é permitido alterar o saldo da conta.'})
        return super().update(request, *args, **kwargs)
