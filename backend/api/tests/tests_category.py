from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from backend.api.categories.models import Category


class CategoryTestCase(TestCase):
    """
    Testes unitários para o modelo Category e seus endpoints.
    """

    def setUp(self):
        """
        Configuração inicial para os testes.
        """
        self.client = APIClient()
        self.valid_payload = {
            'name': 'Alimentação',
            'color': '#FF5733',
            'icon': 'food',
            'is_archived': False,
            'subcategory': None  # Inicialmente sem subcategoria
        }

        # Categoria principal para testes de subcategoria
        self.main_category = Category.objects.create(
            name='Transporte',
            color='#33A1FF',
            icon='car',
            is_archived=False
        )

    def test_create_category_success(self):
        """
        Testa criação de categoria com dados válidos.
        """
        response = self.client.post(
            '/api/v1/categories/',
            self.valid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)  # main_category + nova
        self.assertEqual(response.json().get('name'), 'Alimentação')
        self.assertEqual(response.json().get('color'), '#FF5733')

    def test_create_category_invalid_color_format(self):
        """
        Testa criação de categoria com formato de cor inválido.
        """
        invalid_payload = self.valid_payload.copy()
        invalid_payload['color'] = 'FF5733'  # Sem #

        response = self.client.post(
            '/api/v1/categories/',
            invalid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('color', response.json())

    def test_create_category_invalid_color_length(self):
        """
        Testa criação de categoria com cor de comprimento inválido.
        """
        invalid_payload = self.valid_payload.copy()
        invalid_payload['color'] = '#FF573'  # Muito curto

        response = self.client.post(
            '/api/v1/categories/',
            invalid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('color', response.json())

    def test_create_category_invalid_color_hex(self):
        """
        Testa criação de categoria com cor de contendo hexadecimal inválido.
        """
        invalid_payload = self.valid_payload.copy()
        invalid_payload['color'] = '#AAAZZZ'  # Z não é hexadecimal

        response = self.client.post(
            '/api/v1/categories/',
            invalid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('color', response.json())

    def test_create_category_empty_name(self):
        """
        Testa criação de categoria com nome vazio.
        """
        invalid_payload = self.valid_payload.copy()
        invalid_payload['name'] = '   '  # Apenas espaços

        response = self.client.post(
            '/api/v1/categories/',
            invalid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.json())

    def test_create_subcategory_success(self):
        """
        Testa criação de subcategoria com referência válida.
        """
        subcategory_payload = self.valid_payload.copy()
        subcategory_payload.update({
            'name': 'Combustível',
            'subcategory': self.main_category.id
        })

        response = self.client.post(
            '/api/v1/categories/',
            subcategory_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json().get(
            'subcategory'), self.main_category.id)

    def test_create_subcategory_circular_reference(self):
        """
        Testa prevenção de referência circular em subcategorias.
        """
        # Primeiro cria uma categoria
        category_data = self.valid_payload.copy()
        response = self.client.post(
            '/api/v1/categories/',
            category_data,
            format='json'
        )
        category_id = response.json().get('id')

        # Tenta fazer ela ser subcategoria de si mesma
        update_payload = {'subcategory': category_id}
        response = self.client.patch(
            f'/api/v1/categories/{category_id}/',
            update_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('subcategory', response.json())

    def test_update_category_success(self):
        """
        Testa atualização de categoria com dados válidos.
        """
        category = Category.objects.create(**self.valid_payload)
        update_payload = {
            'name': 'Alimentação Atualizada',
            'color': '#FF0000'
        }

        response = self.client.patch(
            f'/api/v1/categories/{category.id}/',
            update_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get('name'), 'Alimentação Atualizada')
        self.assertEqual(response.json().get('color'), '#FF0000')

    def test_list_categories_default_categories_actived(self):
        """
        Testa listagem de categorias padrão.
        """
        # Cria categoria ativa
        Category.objects.create(**self.valid_payload)

        # Cria categoria arquivada
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Category.objects.create(**archived_payload)

        response = self.client.get('/api/v1/categories/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 2 categorias (main_category + nova)
        self.assertEqual(len(response.json().get('results')), 2)

    def test_list_categories_only_by_name(self):
        """
        Testa listagem de categorias por nome
        """
        # Cria categoria ativa
        Category.objects.create(**self.valid_payload)

        # Cria categoria arquivada, com mesmo nome da ativa
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Category.objects.create(**archived_payload)

        response = self.client.get('/api/v1/categories/?name=Aliment')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 1 categoria, a ativa
        self.assertEqual(len(response.json().get('results')), 1)

    def test_list_categories_only_archived(self):
        """
        Testa listagem de categorias mostrando somente arquivadas.
        """
        # Cria categoria ativa
        Category.objects.create(**self.valid_payload)

        # Cria categoria arquivada
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Category.objects.create(**archived_payload)

        response = self.client.get(
            '/api/v1/categories/?only_archived=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar todas as 1 categorias
        self.assertEqual(len(response.json().get('results')), 1)

    def test_delete_category_archives_instead(self):
        """
        Testa que delete arquiva a categoria ao invés de deletar.
        """
        category = Category.objects.create(**self.valid_payload)

        response = self.client.delete(f'/api/v1/categories/{category.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('arquivada', response.json().get('detail'))

        # Verifica se a categoria foi arquivada
        category.refresh_from_db()
        self.assertTrue(category.is_archived)

    def test_delete_nonexistent_category(self):
        """
        Testa delete de categoria inexistente.
        """
        response = self.client.delete('/api/v1/categories/999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_category_str_representation(self):
        """
        Testa representação string do modelo Category.
        """
        category = Category.objects.create(**self.valid_payload)
        self.assertEqual(str(category), 'Alimentação')

        # Testa representação com subcategoria
        subcategory = Category.objects.create(
            name='Combustível',
            color='#00FF00',
            icon='gas',
            subcategory=self.main_category
        )
        self.assertEqual(str(subcategory), 'Transporte > Combustível')

    def test_category_model_delete_raises_error(self):
        """
        Testa que o método delete do modelo levanta NotImplementedError.
        """
        category = Category.objects.create(**self.valid_payload)

        with self.assertRaises(NotImplementedError):
            category.delete()

    def test_unique_together_constraint(self):
        """
        Testa restrição de unicidade por nome e subcategoria.
        """
        # Cria primeira categoria
        Category.objects.create(**self.valid_payload)

        # Tenta criar categoria com mesmo nome (deve falhar)
        with self.assertRaises(Exception):
            Category.objects.create(**self.valid_payload)
