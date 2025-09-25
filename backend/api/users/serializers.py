from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer para registro de novos usuários.
    """
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[validate_password],
        help_text="Senha deve ter pelo menos 8 caracteres."
    )
    password_confirm = serializers.CharField(
        write_only=True,
        help_text="Confirmação da senha."
    )

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'social_name', 'cpf',
            'phone', 'email', 'password', 'password_confirm'
        ]

    def validate_cpf(self, value):
        """
        Valida se o CPF já não está em uso por outro usuário.
        """
        # Remove formatação
        cpf_clean = ''.join(filter(str.isdigit, value))

        if User.objects.filter(cpf=cpf_clean).exists():
            raise serializers.ValidationError("Este CPF já está registrado.")

        return cpf_clean

    def validate_email(self, value):
        """
        Valida se o email já não está em uso por outro usuário.
        """
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("Este email já está registrado.")

        return value.lower()

    def validate(self, attrs):
        """
        Valida se as senhas coincidem.
        """
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'As senhas não coincidem.'
            })

        # Remove password_confirm dos dados
        attrs.pop('password_confirm')
        return attrs

    def create(self, validated_data):
        """
        Cria um novo usuário com senha hash.
        """
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer para login de usuários.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """
        Valida as credenciais do usuário.
        """
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                username=email.lower(),
                password=password
            )

            if not user:
                raise serializers.ValidationError(
                    'Email ou senha inválidos.'
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    'Conta de usuário desativada.'
                )

            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                'Deve incluir "email" e "password".'
            )


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer para visualização e edição do perfil do usuário.
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    display_name = serializers.CharField(
        source='get_display_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'social_name', 'cpf',
            'phone', 'email', 'full_name', 'display_name',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'cpf', 'email',
                            'is_active', 'created_at', 'updated_at']

    def validate_cpf(self, value):
        """
        Impede alteração do CPF após criação.
        """
        if self.instance and self.instance.cpf != value:
            raise serializers.ValidationError("O CPF não pode ser alterado.")
        return value

    def validate_email(self, value):
        """
        Impede alteração do email após criação.
        """
        if self.instance and self.instance.email != value.lower():
            raise serializers.ValidationError("O email não pode ser alterado.")
        return value.lower()


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer para alteração de senha.
    """
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        """
        Valida se a senha atual está correta.
        """
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Senha atual incorreta.")
        return value

    def validate(self, attrs):
        """
        Valida se as novas senhas coincidem.
        """
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'As senhas não coincidem.'
            })
        return attrs

    def save(self) -> User:
        """
        Atualiza a senha do usuário.
        """
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])  # type: ignore
        user.save()
        return user


class TokenSerializer(serializers.Serializer):
    """
    Serializer para resposta de tokens JWT.
    """
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserProfileSerializer()

    @staticmethod
    def get_token_for_user(user):
        """
        Gera tokens JWT para o usuário.
        """
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),  # type: ignore
            'refresh': str(refresh),
            'user': UserProfileSerializer(user).data
        }
