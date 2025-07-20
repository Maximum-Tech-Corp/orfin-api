from django.db import models


class Account(models.Model):
    # TODO change to enum: Account types e colors
    ACCOUNT_TYPES = [
        ('corrente', 'Corrente'),
        ('dinheiro', 'Dinheiro'),
        ('poupanca', 'Poupança'),
        ('investimentos', 'Investimentos'),
        ('outros', 'Outros'),
    ]

    COLORS = [
        ('#FF0000', 'Red'),
        ('#00FF00', 'Green'),
        ('#0000FF', 'Blue'),
        ('#FFFF00', 'Yellow'),
        ('#FF00FF', 'Magenta'),
        ('#00FFFF', 'Cyan'),
    ]

    id = models.AutoField(primary_key=True)
    bank_name = models.CharField(max_length=30)
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=200, blank=True, null=True)
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPES)
    color = models.CharField(max_length=7, choices=COLORS)
    include_calc = models.BooleanField(default=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    is_archived = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_archived:
            self.include_calc = False
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Não é permitido deletar contas.")

    class Meta:
        db_table = 'account'
        verbose_name = 'Conta'
        verbose_name_plural = 'Contas'
