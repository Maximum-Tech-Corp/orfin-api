from django.urls import include, path

urlpatterns = [
    # Autenticação
    path('auth/', include('backend.api.users.urls')),

    # Entidades principais
    path('', include('backend.api.accounts.urls')),
    path('', include('backend.api.categories.urls')),
    path('', include('backend.api.relatives.urls')),

    # Transações e recorrência
    path('', include('backend.api.transactions.urls')),
]
