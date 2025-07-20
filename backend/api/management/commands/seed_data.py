from decimal import Decimal

from django.core.management.base import BaseCommand
from faker import Faker

from backend.api.accounts.models import Account
from backend.api.categories.models import Category


class Command(BaseCommand):
    help = 'Seed database with sample data'

    def __init__(self):
        super().__init__()
        self.fake = Faker('pt_BR')

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')

        # Limpa dados existentes
        self.stdout.write('Cleaning existing data...')
        Category.objects.all().delete()
        Account.objects.all().delete()

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

        for category_data in categories_data:
            # Cria categoria principal com cor aleatória
            main_category = Category.objects.create(
                name=category_data['name'],
                color=self.fake.random_element(colors),
                icon=category_data['icon']
            )

            # Cria subcategorias
            for subcategory_name in category_data['subcategories']:
                Category.objects.create(
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

        # Cria 4 contas com dados parcialmente aleatórios
        for _ in range(4):
            bank = self.fake.random_element(banks)
            account_type = self.fake.random_element(Account.ACCOUNT_TYPES)[0]

            Account.objects.create(
                bank_name=bank,
                name=f'Conta {self.fake.word().capitalize()}',
                description=self.fake.text(max_nb_chars=150),
                account_type=account_type,
                color=self.fake.random_element(colors),
                balance=Decimal(str(self.fake.random.uniform(
                    100, 15000))).quantize(Decimal('.01')),
                include_calc=self.fake.boolean(chance_of_getting_true=80),
                is_archived=self.fake.boolean(chance_of_getting_true=20)
            )

        self.stdout.write(self.style.SUCCESS('Successfully seeded database'))
