from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_queryset(self):
        """
        Filtros do GET:
        Mostra apenas categorias do usuário autenticado
        Se X-Relative-Id no header, filtra por perfil específico
        Por padrão, mostra todas as categorias ativas
        """

        # Filtra apenas categorias do usuário autenticado
        queryset = Category.objects.filter(user=self.request.user)

        # Filtro por perfil se X-Relative-Id estiver presente no header
        relative_id = self.request.headers.get('X-Relative-Id')
        if relative_id:
            try:
                from backend.api.relatives.models import Relative
                relative = Relative.objects.get(id=relative_id, user=self.request.user)
                queryset = queryset.filter(relative=relative)
            except Relative.DoesNotExist:
                # Se perfil não existir, retorna queryset vazio
                return Category.objects.none()

        # Se houver parâmetro 'only_archived'=true, retorna somente as arquivadas
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

    def perform_create(self, serializer):
        """
        Associa a categoria ao usuário autenticado durante a criação.
        """
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """
        Sobrescreve o método destroy para implementar soft delete.
        Arquiva a categoria ao invés de deletá-la fisicamente.
        Arquiva também as categorias filhas.
        """
        try:
            # Arquiva a categoria
            category = self.get_object()
            category.is_archived = True
            category.save()

            # Procura por categorias filhas do mesmo usuário e perfil e as arquiva também
            subcategories = Category.objects.filter(
                user=self.request.user,
                relative=category.relative,
                subcategory=category.id
            )
            if subcategories.exists():
                subcategories.update(is_archived=True)
                message = "Categoria e suas subcategorias foram arquivadas com sucesso."
            else:
                message = "Categoria arquivada com sucesso."

            return Response(
                {"detail": message},
                status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {"detail": "Categoria não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )
