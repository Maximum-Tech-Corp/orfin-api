from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Drop all the database tables and create them'

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            # Drop all the tables
            self.stdout.write(self.style.WARNING('Dropping all tables...'))
            cursor.execute("DROP SCHEMA public CASCADE;")

            # Recrate the public schema
            self.stdout.write(self.style.WARNING(
                'Recreating public schema...'))
            cursor.execute("CREATE SCHEMA public;")

        self.stdout.write(self.style.SUCCESS('Database reset complete!'))

        # Execute migrations
        self.stdout.write(self.style.WARNING('Running migrations...'))
        from django.core.management import call_command
        call_command('migrate')
        self.stdout.write(self.style.SUCCESS('Migrations complete!'))
