from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .users.models import User
from .accounts.models import Account
from .categories.models import Category
from .transactions.models import Transaction, RecurringRule
from .credit_cards.models import CreditCard, Invoice


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin customizado para o modelo User.
    """
    list_display = ['email', 'first_name', 'last_name', 'social_name', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'social_name', 'cpf']
    ordering = ['-created_at']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informações Pessoais', {
            'fields': ('first_name', 'last_name', 'social_name', 'cpf', 'phone')
        }),
        ('Permissões', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Datas importantes', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'social_name', 'cpf', 'phone', 'password1', 'password2'),
        }),
    )

    readonly_fields = ['created_at', 'updated_at', 'date_joined']

    # Remove username do form
    username = None


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """
    Admin para o modelo Account.
    """
    list_display = ['name', 'user', 'bank_name', 'account_type', 'balance', 'is_archived', 'created_at']
    list_filter = ['account_type', 'is_archived', 'include_calc', 'created_at']
    search_fields = ['name', 'bank_name', 'user__email', 'user__first_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Admin para o modelo Category.
    """
    list_display = ['name', 'user', 'type_category', 'subcategory', 'color', 'icon', 'is_archived', 'created_at']
    list_filter = ['type_category', 'is_archived', 'created_at']
    search_fields = ['name', 'user__email', 'user__first_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """
    Admin para o modelo Transaction.
    """
    list_display = [
        'description', 'user', 'type', 'amount', 'date', 'is_paid', 'created_at'
    ]
    list_filter = ['type', 'is_paid', 'created_at']
    search_fields = ['description', 'user__email', 'user__first_name']
    ordering = ['-date', '-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(RecurringRule)
class RecurringRuleAdmin(admin.ModelAdmin):
    """
    Admin para o modelo RecurringRule.
    """
    list_display = [
        'description', 'user', 'type', 'frequency', 'interval', 'amount', 'is_active', 'created_at'
    ]
    list_filter = ['type', 'frequency', 'is_active', 'created_at']
    search_fields = ['description', 'user__email', 'user__first_name']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(CreditCard)
class CreditCardAdmin(admin.ModelAdmin):
    """
    Admin para o modelo CreditCard.
    """
    list_display = [
        'name', 'user', 'limit', 'closing_day', 'due_day', 'is_archived', 'created_at'
    ]
    list_filter = ['is_archived', 'created_at']
    search_fields = ['name', 'user__email', 'user__first_name']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """
    Admin para o modelo Invoice.
    """
    list_display = [
        'credit_card', 'reference_month', 'reference_year',
        'status', 'due_date', 'total_amount', 'paid_at', 'created_at'
    ]
    list_filter = ['status', 'reference_year', 'created_at']
    search_fields = ['credit_card__name', 'credit_card__user__email']
    ordering = ['-reference_year', '-reference_month']
    readonly_fields = ['id', 'total_amount', 'paid_at', 'paid_via_account', 'created_at', 'updated_at']
