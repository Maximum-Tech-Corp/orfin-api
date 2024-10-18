from django.urls import include, path

urlpatterns = [
    path('', include('backend.api.accounts.urls')),
]
