from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models

from backend.api.utils.validators import validate_cpf


class UserManager(BaseUserManager):
    """
    Manager customizado para o modelo User.
    Gerencia criação de usuários sem campo username.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Cria e salva um usuário comum com email e senha.
        """
        if not email:
            raise ValueError('O email é obrigatório')

        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Cria e salva um superusuário com email e senha.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser deve ter is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser deve ter is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Modelo de usuário customizado para o sistema Orfin.
    Extende o AbstractUser do Django com campos específicos.
    """

    # Removendo o campo username pois usaremos email para login
    username = None

    # Campos obrigatórios
    first_name = models.CharField('Primeiro Nome', max_length=150)
    last_name = models.CharField('Sobrenome', max_length=150)
    social_name = models.CharField('Nome Social', max_length=150)
    cpf = models.CharField('CPF', max_length=11, unique=True)
    phone = models.CharField('Telefone', max_length=15, blank=True, null=True)
    email = models.EmailField('Email', unique=True)

    # Campos de auditoria
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    # Configuração para usar email como campo de login
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'social_name', 'cpf']

    # Manager customizado
    objects = UserManager()  # type: ignore

    class Meta:
        db_table = 'auth_user_custom'
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering = ['-created_at']

    def clean(self):
        """
        Valida os dados do usuário antes de salvar.
        """
        super().clean()

        # Valida CPF
        if self.cpf:
            validate_cpf(self.cpf)

        # Remove espaços em branco dos campos de texto
        if self.first_name:
            self.first_name = self.first_name.strip()
        if self.last_name:
            self.last_name = self.last_name.strip()
        if self.social_name:
            self.social_name = self.social_name.strip()

        # Valida que todos os campos obrigatórios estão preenchidos
        if not self.first_name:
            raise ValidationError(
                {'first_name': 'O primeiro nome é obrigatório.'})
        if not self.last_name:
            raise ValidationError({'last_name': 'O sobrenome é obrigatório.'})
        if not self.social_name:
            raise ValidationError(
                {'social_name': 'O nome social é obrigatório.'})
        if not self.cpf:
            raise ValidationError({'cpf': 'O CPF é obrigatório.'})
        if not self.email:
            raise ValidationError({'email': 'O email é obrigatório.'})

    def save(self, *args, **kwargs):
        """
        Sobrescreve o método save para incluir validação.
        """
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """
        Impede exclusão física do usuário.
        """
        raise NotImplementedError(
            'Não é possível excluir um usuário. Use is_active = False para desativar.'
        )

    def soft_delete(self):
        """
        Método para desativar o usuário.
        """
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])

    def get_full_name(self):
        """
        Retorna o nome completo do usuário.
        """
        return f"{self.first_name} {self.last_name}"

    def get_display_name(self):
        """
        Retorna o nome social ou nome completo para exibição.
        """
        return self.social_name or self.get_full_name()

    def __str__(self):
        return f"{self.get_display_name()} ({self.email})"
