from django.urls import path

from .views import (ChangePasswordView, CustomTokenObtainPairView,
                    CustomTokenRefreshView, UserLoginView, UserProfileView,
                    UserRegistrationView, deactivate_user,
                    user_profile_summary)

urlpatterns = [
    # Autenticação
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('login/', UserLoginView.as_view(), name='user-login'),

    # Perfil do usuário
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('me/', user_profile_summary, name='user-profile-summary'),

    # Gerenciamento de conta
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('deactivate/', deactivate_user, name='deactivate-user'),

    # JWT Tokens
    path('token/', CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
]
