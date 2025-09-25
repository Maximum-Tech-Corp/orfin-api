from django.urls import include, path

urlpatterns = [
    # Autenticação
    path('auth/', include('backend.api.users.urls')),

    # Entidades principais
    path('', include('backend.api.accounts.urls')),
    path('', include('backend.api.categories.urls')),
]
