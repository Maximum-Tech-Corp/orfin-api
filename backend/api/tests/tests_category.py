from django.core.exceptions import ValidationError
from rest_framework import status

from backend.api.categories.models import Category

from .base import BaseAuthenticatedTestCase
from .constants import VALID_HEX_COLORS, get_category_data


class CategoryTestCase(BaseAuthenticatedTestCase):
    def setUp(self):
        super().setUp()  # Chama o setUp da classe base (autentica automaticamente)
        self.valid_payload = get_category_data()

        # Categoria principal para testes de subcategoria
        self.main_category = Category.objects.create(
            user=self.user,
            name='Transporte',
            color='#33A1FF',
            icon='car',
            is_archived=False
        )

    def test_create_category_success(self):
        response = self.client.post(
            '/api/v1/categories/',
            self.valid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)  # main_category + nova
        self.assertEqual(response.json().get('name'), 'Alimentação')
        self.assertEqual(response.json().get('color'), '#FF5733')

    def test_cannot_create_category_invalid_color_format(self):
        invalid_payload = self.valid_payload.copy()
        invalid_payload['color'] = 'FF5733'  # Sem #

        response = self.client.post(
            '/api/v1/categories/',
            invalid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('color', response.json())

    def test_cannot_create_category_invalid_color_length(self):
        invalid_payload = self.valid_payload.copy()
        invalid_payload['color'] = '#FF573'  # Muito curto

        response = self.client.post(
            '/api/v1/categories/',
            invalid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('color', response.json())

    def test_cannot_create_category_invalid_color_hex(self):
        invalid_payload = self.valid_payload.copy()
        invalid_payload['color'] = '#AAAZZZ'  # Z não é hexadecimal

        response = self.client.post(
            '/api/v1/categories/',
            invalid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('color', response.json())

    def test_cannot_create_category_empty_name(self):
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

    def test_cannot_create_subcategory_with_different_user(self):
        category = Category.objects.create(
            user=self.user, **self.valid_payload)

        other_user = self.create_additional_user()
        subcategory_payload = self.valid_payload.copy()
        subcategory_payload.update({
            'name': 'Combustível',
            'subcategory': category,
        })

        with self.assertRaises(ValidationError) as cm:
            Category.objects.create(user=other_user, **subcategory_payload)

        self.assertIn('subcategory', cm.exception.message_dict)
        self.assertIn('A categoria pai deve pertencer ao mesmo usuário.',
                      cm.exception.message_dict['subcategory'])

    def test_cannot_create_subcategory_circular_reference(self):
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

    def test_cannot_create_duplicate_category_same_level(self):
        # Cria primeira categoria (sem subcategoria)
        Category.objects.create(user=self.user, **self.valid_payload)

        # Tenta criar outra categoria com mesmo nome e sem subcategoria
        response = self.client.post(
            '/api/v1/categories/',
            self.valid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())

    def test_can_create_duplicate_category_different_levels(self):
        # Cria primeira categoria (sem subcategoria)
        Category.objects.create(user=self.user, **self.valid_payload)

        # Cria segunda categoria com mesmo nome, mas como subcategoria
        duplicate_payload = self.valid_payload.copy()
        duplicate_payload['subcategory'] = self.main_category.id

        response = self.client.post(
            '/api/v1/categories/',
            duplicate_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_create_nested_subcategory(self):
        # Cria primeira subcategoria
        first_subcategory_payload = self.valid_payload.copy()
        first_subcategory_payload.update({
            'subcategory': self.main_category
        })

        first_subcategory_payload = Category.objects.create(
            user=self.user,
            **first_subcategory_payload)
        first_subcategory_payload.refresh_from_db()

        # Tenta criar subcategoria da subcategoria
        second_subcategory_payload = self.valid_payload.copy()
        second_subcategory_payload.update({
            'name': 'Combustível',
            'subcategory': first_subcategory_payload.id
        })

        response = self.client.post(
            '/api/v1/categories/',
            second_subcategory_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('subcategory', response.json()['error'])

    def test_update_category_success(self):
        category = Category.objects.create(
            user=self.user, **self.valid_payload)
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

    def test_can_update_category_duplicate_name_same_level(self):
        # Cria primeira subcategoria
        first_subcategory_payload = self.valid_payload.copy()
        first_subcategory_payload.update({
            'subcategory': self.main_category
        })

        first_subcategory_payload = Category.objects.create(
            user=self.user,
            **first_subcategory_payload)
        first_subcategory_payload.refresh_from_db()

        # Tenta criar subcategoria da subcategoria
        second_subcategory_payload = self.valid_payload.copy()
        second_subcategory_payload.update({
            'name': 'Combustível',
            'subcategory': self.main_category
        })

        second_subcategory_payload = Category.objects.create(
            user=self.user,
            **second_subcategory_payload)
        second_subcategory_payload.refresh_from_db()

        # Tenta atualizar category2 para ter o mesmo nome de category1
        update_payload = {'subcategory': first_subcategory_payload.id}
        response = self.client.patch(
            f'/api/v1/categories/{second_subcategory_payload.id}/',
            update_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_update_to_nested_subcategory(self):
        # Cria primeira subcategoria
        subcategory = Category.objects.create(
            user=self.user,
            name='Subcategoria',
            color='#33FF57',
            icon='sub',
            subcategory=self.main_category
        )

        # Cria categoria para tentar transformar em sub-subcategoria
        category = Category.objects.create(
            user=self.user, **self.valid_payload)

        # Tenta atualizar para ser subcategoria da subcategoria
        update_payload = {'subcategory': subcategory.id}
        response = self.client.patch(
            f'/api/v1/categories/{category.id}/',
            update_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('subcategory', response.json()['error'])

    def test_list_categories_default_categories_actived(self):
        # Cria categoria ativa
        Category.objects.create(user=self.user, **self.valid_payload)

        # Cria categoria arquivada
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Category.objects.create(user=self.user, **archived_payload)

        response = self.client.get('/api/v1/categories/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 2 categorias (main_category + nova)
        self.assertEqual(len(response.json().get('results')), 2)

    def test_list_categories_only_by_name(self):
        # Cria categoria ativa
        Category.objects.create(user=self.user, **self.valid_payload)

        # Cria categoria arquivada, com mesmo nome da ativa
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Category.objects.create(user=self.user, **archived_payload)

        response = self.client.get('/api/v1/categories/?name=Aliment')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 1 categoria, a ativa
        self.assertEqual(len(response.json().get('results')), 1)

    def test_list_categories_only_archived(self):
        # Cria categoria ativa
        Category.objects.create(user=self.user, **self.valid_payload)

        # Cria categoria arquivada
        archived_payload = self.valid_payload.copy()
        archived_payload.update({
            'name': 'Arquivada',
            'is_archived': True
        })
        Category.objects.create(user=self.user, **archived_payload)

        response = self.client.get(
            '/api/v1/categories/?only_archived=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar todas as 1 categorias
        self.assertEqual(len(response.json().get('results')), 1)

    def test_delete_category_archives_instead(self):
        category = Category.objects.create(
            user=self.user, **self.valid_payload)

        response = self.client.delete(f'/api/v1/categories/{category.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('arquivada', response.json().get('detail'))

        # Verifica se a categoria foi arquivada
        category.refresh_from_db()
        self.assertTrue(category.is_archived)

    def test_when_archiving_category_archives_subcategories(self):
        # Cria categoria pai
        parent_category = Category.objects.create(
            user=self.user, **self.valid_payload)

        # Cria algumas subcategorias
        subcategory_payload = self.valid_payload.copy()
        subcategory_payload.update({
            'name': 'Subcategoria 1',
            'subcategory': parent_category
        })
        subcategory1 = Category.objects.create(
            user=self.user, **subcategory_payload)

        subcategory_payload['name'] = 'Subcategoria 2'
        subcategory2 = Category.objects.create(
            user=self.user, **subcategory_payload)

        # Arquiva a categoria pai
        response = self.client.delete(
            f'/api/v1/categories/{parent_category.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('subcategorias', response.json().get('detail'))

        # Verifica se as subcategorias foram arquivadas
        subcategory1.refresh_from_db()
        subcategory2.refresh_from_db()
        self.assertTrue(subcategory1.is_archived)
        self.assertTrue(subcategory2.is_archived)

    def test_delete_nonexistent_category(self):
        response = self.client.delete('/api/v1/categories/999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_category_str_representation(self):
        category = Category.objects.create(
            user=self.user, **self.valid_payload)
        self.assertEqual(str(category), 'Alimentação')

        # Testa representação com subcategoria
        subcategory = Category.objects.create(
            user=self.user,
            name='Combustível',
            color='#00FF00',
            icon='gas',
            subcategory=self.main_category
        )
        self.assertEqual(str(subcategory), 'Transporte > Combustível')

    def test_category_model_delete_raises_error(self):
        category = Category.objects.create(
            user=self.user, **self.valid_payload)

        with self.assertRaises(NotImplementedError):
            category.delete()

    def test_unique_together_constraint(self):
        # Cria primeira categoria
        Category.objects.create(user=self.user, **self.valid_payload)

        # Tenta criar categoria com mesmo nome (deve falhar)
        with self.assertRaises(Exception):
            Category.objects.create(user=self.user, **self.valid_payload)

    def test_user_can_only_see_own_categories(self):
        # Cria categoria para o usuário atual
        Category.objects.create(user=self.user, **self.valid_payload)

        # Cria outro usuário e uma categoria para ele
        other_user = self.create_additional_user()
        other_payload = self.valid_payload.copy()
        other_payload['name'] = 'Categoria do Outro Usuário'
        Category.objects.create(user=other_user, **other_payload)

        # Faz requisição como usuário atual
        response = self.client.get('/api/v1/categories/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Deve retornar apenas 2 categorias (main_category + nova)
        self.assertEqual(len(response.json().get('results')), 2)

    def test_user_cannot_access_other_user_category(self):
        # Cria outro usuário e uma categoria para ele
        other_user = self.create_additional_user()
        other_payload = self.valid_payload.copy()
        other_payload['name'] = 'Categoria do Outro Usuário'
        other_category = Category.objects.create(
            user=other_user, **other_payload)

        # Tenta acessar categoria do outro usuário
        response = self.client.get(f'/api/v1/categories/{other_category.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_use_other_user_category_as_subcategory(self):
        # Cria outro usuário e uma categoria para ele
        other_user = self.create_additional_user()
        other_category = Category.objects.create(
            user=other_user,
            name='Categoria do Outro Usuário',
            color='#FF0000',
            icon='other'
        )

        # Tenta criar categoria usando categoria do outro usuário como pai
        invalid_payload = self.valid_payload.copy()
        invalid_payload['subcategory'] = other_category.id

        response = self.client.post(
            '/api/v1/categories/',
            invalid_payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_user_cannot_access_categories(self):
        # Remove autenticação
        self.unauthenticate()

        response = self.client.get('/api/v1/categories/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
