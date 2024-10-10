from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # path('', include('backend.api.urls', namespace='api')),  # noqa E501
    path('admin/', admin.site.urls),  # noqa E501
]
