from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Relative
from .serializers import RelativeListSerializer, RelativeSerializer


class RelativeViewSet(viewsets.ModelViewSet):
    """
    ViewSet para operações CRUD da entidade Relative.
    Permite criar, listar, recuperar, atualizar e arquivar perfis.
    """
    serializer_class = RelativeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_archived']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """
        Retorna apenas os perfis do usuário logado.
        """
        return Relative.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """
        Retorna o serializer apropriado baseado na ação.
        """
        if self.action == 'list':
            return RelativeListSerializer
        return RelativeSerializer

    def destroy(self, request, *args, **kwargs):
        """
        Arquiva o perfil ao invés de deletá-lo fisicamente.
        """
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """
        Desarquiva um perfil.
        """
        instance = self.get_object()
        if not instance.is_archived:
            return Response(
                {'detail': 'Perfil já está ativo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.is_archived = False
        instance.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Lista apenas os perfis ativos (não arquivados).
        """
        queryset = self.get_queryset().filter(is_archived=False)
        serializer = RelativeListSerializer(queryset, many=True)
        return Response(serializer.data)
