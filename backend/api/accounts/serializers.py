from rest_framework import serializers

from .models import Account


class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True  # O campo será exigido na requisição
    )

    class Meta:
        model = Account
        fields = '__all__'
        read_only_fields = ['user']  # Usuário é definido automaticamente

    def validate(self, data):
        if data.get('is_archived') and data.get('include_calc', True):
            raise serializers.ValidationError(
                "Não é permitido manter include_calc true e manter is_archived false.")
        return data
