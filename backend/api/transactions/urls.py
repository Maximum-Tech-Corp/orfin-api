from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RecurringRuleViewSet, TransactionViewSet

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'recurring-rules', RecurringRuleViewSet, basename='recurring-rule')

urlpatterns = [
    path('', include(router.urls)),
]
