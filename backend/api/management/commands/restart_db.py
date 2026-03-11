from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Drop all the database tables and create them'

    def add_arguments(self, parser):
        # Parâmetro opcional para popular o banco com dados iniciais de desenvolvimento
        parser.add_argument(
            '--seed',
            action='store_true',
            help='Após resetar e migrar, cria usuário padrão com perfis e conta para desenvolvimento.',
        )

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            # Remove todas as tabelas
            self.stdout.write(self.style.WARNING('Dropping all tables...'))
            cursor.execute("DROP SCHEMA public CASCADE;")

            # Recria o schema público
            self.stdout.write(self.style.WARNING(
                'Recreating public schema...'))
            cursor.execute("CREATE SCHEMA public;")

        self.stdout.write(self.style.SUCCESS('Database reset complete!'))

        # Executa as migrações
        self.stdout.write(self.style.WARNING('Running migrations...'))
        from django.core.management import call_command
        call_command('migrate')
        self.stdout.write(self.style.SUCCESS('Migrations complete!'))

        # Se --seed foi passado, cria dados iniciais de desenvolvimento
        if kwargs['seed']:
            self._seed_dev_data()

    def _seed_dev_data(self):
        """
        Cria dados iniciais para desenvolvimento local:
        - Usuário diegoifce@gmail.com com senha qwe123
        - Perfis Diego e Cirlene vinculados ao usuário
        - Conta Santander vinculada ao perfil Diego
        """
        from backend.api.accounts.models import Account
        from backend.api.relatives.models import Relative
        from backend.api.users.models import User

        self.stdout.write(self.style.WARNING('Seeding dev data...'))

        # Cria o usuário principal de desenvolvimento
        user = User.objects.create_user(
            email='diegoifce@gmail.com',
            password='qwe123',
            first_name='Diego',
            last_name='Masin',
            social_name='Diego Masin',
            cpf='52998224725',
            phone='85999999999',
        )
        self.stdout.write(f'  Usuário criado: {user.email}')

        # Cria perfil Diego
        relative_diego = Relative.objects.create(
            user=user,
            name='Diego',
            image_num=1,
            is_archived=False,
        )
        self.stdout.write(f'  Perfil criado: {relative_diego.name}')

        # Cria perfil Cirlene
        relative_cirlene = Relative.objects.create(
            user=user,
            name='Cirlene',
            image_num=2,
            is_archived=False,
        )
        self.stdout.write(f'  Perfil criado: {relative_cirlene.name}')

        # Cria conta Santander para o perfil Diego
        account = Account.objects.create(
            user=user,
            relative=relative_diego,
            bank_name='Santander',
            name='Santander',
            description='Conta corrente Santander',
            account_type='corrente',
            color='#EC0000',
            balance=Decimal('0.00'),
            include_calc=True,
            is_archived=False,
        )
        self.stdout.write(f'  Conta criada: {account.name} ({relative_diego.name})')

        self.stdout.write(self.style.SUCCESS('Dev seed complete!'))
