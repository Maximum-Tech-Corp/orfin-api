from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import (TokenObtainPairView,
                                            TokenRefreshView)

from .models import User
from .serializers import (ChangePasswordSerializer, TokenSerializer,
                          UserLoginSerializer, UserProfileSerializer,
                          UserRegistrationSerializer)


class UserRegistrationView(generics.CreateAPIView):
    """
    View para registro de novos usuários.
    Endpoint: POST /api/v1/auth/register/
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Gerar tokens para o usuário recém-criado
        token_data = TokenSerializer.get_token_for_user(user)

        return Response(
            {
                'message': 'Usuário criado com sucesso.',
                'data': token_data
            },
            status=status.HTTP_201_CREATED
        )


class UserLoginView(generics.GenericAPIView):
    """
    View para login de usuários.
    Endpoint: POST /api/v1/auth/login/
    """
    serializer_class = UserLoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        # Gerar tokens para o usuário
        token_data = TokenSerializer.get_token_for_user(user)

        return Response(
            {
                'message': 'Login realizado com sucesso.',
                'data': token_data
            },
            status=status.HTTP_200_OK
        )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    View para visualização e edição do perfil do usuário.
    Endpoints:
    - GET /api/v1/auth/profile/ - Visualizar perfil
    - PUT/PATCH /api/v1/auth/profile/ - Editar perfil
    """
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {
                'message': 'Perfil atualizado com sucesso.',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )


class ChangePasswordView(generics.GenericAPIView):
    """
    View para alteração de senha do usuário.
    Endpoint: POST /api/v1/auth/change-password/
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                'message': 'Senha alterada com sucesso.'
            },
            status=status.HTTP_200_OK
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deactivate_user(request):
    """
    View para desativar a conta do usuário (soft delete).
    Endpoint: DELETE /api/v1/auth/deactivate/
    """
    user = request.user
    user.soft_delete()

    return Response(
        {
            'message': 'Conta desativada com sucesso.'
        },
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile_summary(request):
    """
    View para resumo do perfil do usuário (versão simplificada).
    Endpoint: GET /api/v1/auth/me/
    """
    user = request.user
    data = {
        'id': user.id,
        'display_name': user.get_display_name(),
        'email': user.email,
        'is_active': user.is_active
    }

    return Response(
        {
            'message': 'Dados do usuário recuperados com sucesso.',
            'data': data
        },
        status=status.HTTP_200_OK
    )


# Views customizadas para JWT
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    View customizada para obtenção de tokens JWT.
    Endpoint: POST /api/v1/auth/token/
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Usar o UserLoginSerializer para validação
        login_serializer = UserLoginSerializer(
            data=request.data,
            context={'request': request}
        )
        login_serializer.is_valid(raise_exception=True)

        user = login_serializer.validated_data['user']  # type: ignore
        token_data = TokenSerializer.get_token_for_user(user)

        return Response(
            {
                'message': 'Tokens gerados com sucesso.',
                'data': token_data
            },
            status=status.HTTP_200_OK
        )


class CustomTokenRefreshView(TokenRefreshView):
    """
    View customizada para renovação de tokens JWT.
    Endpoint: POST /api/v1/auth/token/refresh/
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        return Response(
            {
                'message': 'Token renovado com sucesso.',
                'data': response.data
            },
            status=status.HTTP_200_OK
        )
