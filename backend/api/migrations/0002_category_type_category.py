from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='type_category',
            field=models.CharField(
                choices=[('despesas', 'Despesas'), ('receitas', 'Receitas')],
                default='despesas',
                max_length=10,
            ),
            preserve_default=False,
        ),
    ]
