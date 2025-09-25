from decimal import Decimal

from django.core.management.base import BaseCommand
from faker import Faker

from backend.api.accounts.models import Account
from backend.api.categories.models import Category
from backend.api.users.models import User


class Command(BaseCommand):
    help = 'Seed database with sample data'

    def __init__(self):
        super().__init__()
        self.fake = Faker('pt_BR')

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')

        # Limpa dados existentes
        self.stdout.write('Cleaning existing data...')
        Account.objects.all().delete()
        Category.objects.all().delete()
        # User é deletado por último devido às relações
        User.objects.filter(is_superuser=False).delete()

        # Seed Users
        self.stdout.write('Creating users...')
        users = []

        # Cria 3 usuários de teste
        users_data = [
            {
                'first_name': 'Diego',
                'last_name': 'Masin',
                'social_name': 'Trizayfer',
                'cpf': '60017806330',
                'email': 'diego@email.com',
                'phone': '11999999999'
            },
            {
                'first_name': 'Cirlene',
                'last_name': 'Souto',
                'social_name': 'Cirlene Souto',
                'cpf': '94859400330',
                'email': 'cirlene@email.com',
                'phone': '11888888888'
            },
        ]

        for user_data in users_data:
            user = User.objects.create_user(
                **user_data,
                password='senha123'
            )
            users.append(user)
            self.stdout.write(f'Created user: {user.email}')

        # Seed Categories
        self.stdout.write('Creating categories...')

        # Lista de cores hexadecimais para usar aleatoriamente
        colors = ['#FF5733', '#33FF57', '#3357FF',
                  '#FF33F5', '#33FFF5', '#F5FF33']

        # Categorias principais com subcategorias
        categories_data = [
            {
                'name': 'Moradia',
                'icon': 'home',
                'subcategories': ['Aluguel', 'Condomínio', 'Água', 'Luz', 'Internet']
            },
            {
                'name': 'Transporte',
                'icon': 'car',
                'subcategories': ['Combustível', 'Manutenção', 'Estacionamento', 'Uber']
            },
            {
                'name': 'Alimentação',
                'icon': 'food',
                'subcategories': ['Mercado', 'Restaurante', 'Delivery']
            },
            {
                'name': 'Saúde',
                'icon': 'health',
                'subcategories': ['Plano de Saúde', 'Medicamentos', 'Consultas']
            }
        ]

        # Cria categorias para cada usuário
        for user in users:
            for category_data in categories_data:
                # Cria categoria principal com cor aleatória
                main_category = Category.objects.create(
                    user=user,
                    name=category_data['name'],
                    color=self.fake.random_element(colors),
                    icon=category_data['icon']
                )

                # Cria subcategorias
                for subcategory_name in category_data['subcategories']:
                    Category.objects.create(
                        user=user,
                        name=subcategory_name,
                        color=self.fake.random_element(colors),
                        icon=category_data['icon'],
                        subcategory=main_category
                    )

        # Seed Accounts
        self.stdout.write('Creating accounts...')

        # Bancos brasileiros comuns
        banks = ['Nubank', 'Itaú', 'Bradesco',
                 'Santander', 'Banco do Brasil', 'BTG', 'Inter']

        # Cria 2 contas para cada usuário com dados parcialmente aleatórios
        for user in users:
            for i in range(2):
                bank = self.fake.random_element(banks)
                account_type = self.fake.random_element(
                    Account.ACCOUNT_TYPES)[0]

                Account.objects.create(
                    user=user,
                    bank_name=bank,
                    name=f'Conta {self.fake.word().capitalize()} {i+1}',
                    description=self.fake.text(max_nb_chars=150),
                    account_type=account_type,
                    color=self.fake.random_element(colors),
                    balance=Decimal(str(self.fake.random.uniform(
                        100, 15000))).quantize(Decimal('.01')),
                    include_calc=self.fake.boolean(chance_of_getting_true=80),
                    is_archived=self.fake.boolean(chance_of_getting_true=20)
                )

        self.stdout.write(self.style.SUCCESS('Successfully seeded database'))
