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
        read_only_fields = ['user', 'relative']  # Usuário e relative são definidos automaticamente

    def create(self, validated_data):
        """
        Cria uma nova conta associando automaticamente ao usuário logado e relative do header.
        """
        validated_data['user'] = self.context['request'].user

        # Busca o relative_id do header
        relative_id = self.context['request'].headers.get('X-Relative-Id')
        if relative_id:
            try:
                from backend.api.relatives.models import Relative
                relative = Relative.objects.get(id=relative_id, user=validated_data['user'])
                validated_data['relative'] = relative
            except Relative.DoesNotExist:
                raise serializers.ValidationError("Perfil não encontrado ou não pertence ao usuário.")
        else:
            raise serializers.ValidationError("Header X-Relative-Id é obrigatório.")

        return super().create(validated_data)

    def validate(self, data):
        if data.get('is_archived') and data.get('include_calc', True):
            raise serializers.ValidationError(
                "Não é permitido manter include_calc true e manter is_archived false.")
        return data
