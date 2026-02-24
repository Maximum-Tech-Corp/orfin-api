from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Relative(models.Model):
    """
    Modelo que representa perfils/parentes do usuário.
    """
    name = models.CharField(
        max_length=30,
        verbose_name='Nome'
    )
    image_num = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Imagem'
    )
    is_archived = models.BooleanField(
        default=False,
        verbose_name='Arquivado'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='relatives',
        verbose_name='Usuário'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )

    class Meta:
        db_table = 'relative'
        verbose_name = 'Parente'
        verbose_name_plural = 'Parentes'
        unique_together = ('user', 'name')

    def __str__(self):
        return f"Maria ({self.user.get_display_name()})"

    def clean(self):
        # Verifica se o usuário já possui 3 perfis
        if not self.pk:  # Apenas para novos registros
            existing_count = Relative.objects.filter(user=self.user).count()
            if existing_count >= 3:
                raise ValidationError(
                    'Usuário já possui o limite máximo de 3 perfis de Parentes.')

    def save(self, *args, **kwargs):
        """
        Sobrescreve o método save para incluir validações.
        """
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Impede a exclusão física do registro.
        """
        raise NotImplementedError(
            'Perfis não podem ser deletados. Use o arquivamento.')

    def soft_delete(self):
        """
        Arquiva o perfil ao invés de deletá-lo.
        """
        self.is_archived = True
        self.save()
