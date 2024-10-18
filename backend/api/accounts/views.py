from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Account
from .serializers import AccountSerializer


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Não é permitido deletar contas."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        if 'balance' in request.data:
            raise ValidationError(
                {'balance': 'Não é permitido alterar o saldo da conta.'})
        return super().update(request, *args, **kwargs)
