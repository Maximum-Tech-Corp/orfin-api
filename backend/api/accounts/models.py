from django.conf import settings
from django.core.exceptions import ValidationError
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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='accounts',
        verbose_name='Usuário'
    )
    relative = models.ForeignKey(
        'api.Relative',
        on_delete=models.CASCADE,
        related_name='accounts',
        verbose_name='Parente'
    )
    bank_name = models.CharField(max_length=30)
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=200, blank=True, null=True)
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPES)
    color = models.CharField(max_length=7, choices=COLORS)
    include_calc = models.BooleanField(default=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    is_archived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Valida se já existe conta com mesmo nome para o mesmo usuário e perfil.
        """
        existing = Account.objects.filter(
            user=self.user,
            relative=self.relative,
            name=self.name
        )

        if self.pk:  # Se for update, exclui o próprio registro da validação
            existing = existing.exclude(pk=self.pk)

        if existing.exists():
            raise ValidationError({
                'name': 'Você já possui uma conta com este nome. Use outro nome.'
            })

    def save(self, *args, **kwargs):
        self.clean()
        if self.is_archived:
            self.include_calc = False
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Não é permitido deletar contas.")

    def __str__(self):
        return f"{self.name} - {self.bank_name}"

    class Meta:
        db_table = 'account'
        verbose_name = 'Conta'
        verbose_name_plural = 'Contas'
        # Garante que o usuário não tenha duas contas com o mesmo nome no mesmo perfil
        unique_together = ['user', 'relative', 'name']
