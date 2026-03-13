import re

from rest_framework import serializers

from backend.api.relatives.models import Relative

from .models import CreditCard, Invoice


class CreditCardListSerializer(serializers.ModelSerializer):
    """
    Serializer compacto para listagem de cartões de crédito.
    Expõe campos essenciais para o dashboard e seletor de cartão.
    """

    class Meta:
        model = CreditCard
        fields = [
            'id',
            'name',
            'color',
            'limit',
            'closing_day',
            'due_day',
            'is_archived',
        ]


class CreditCardSerializer(serializers.ModelSerializer):
    """
    Serializer completo para criação e edição de cartões de crédito.
    Associa automaticamente o usuário e o perfil via header X-Relative-Id.
    """

    class Meta:
        model = CreditCard
        fields = '__all__'
        read_only_fields = ['user', 'relative', 'created_at', 'updated_at']

    def validate_color(self, value):
        """
        Garante que a cor seja um hexadecimal válido no formato #RRGGBB.
        """
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError(
                'A cor deve estar no formato hexadecimal #RRGGBB.'
            )
        return value

    def validate_name(self, value):
        """
        Garante que o nome do cartão seja único por usuário e perfil.
        Validação feita no serializer para retornar HTTP 400 com mensagem amigável.
        """
        user = self.context['request'].user
        relative_id = self.context['request'].headers.get('X-Relative-Id')
        qs = CreditCard.objects.filter(user=user, name=value)
        if relative_id:
            qs = qs.filter(relative_id=relative_id)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'Você já possui um cartão com este nome. Use outro nome.'
            )
        return value

    def create(self, validated_data):
        """
        Associa automaticamente o usuário autenticado e o perfil do header X-Relative-Id.
        """
        validated_data['user'] = self.context['request'].user

        relative_id = self.context['request'].headers.get('X-Relative-Id')
        if relative_id:
            try:
                relative = Relative.objects.get(
                    id=relative_id, user=validated_data['user']
                )
                validated_data['relative'] = relative
            except Relative.DoesNotExist:
                raise serializers.ValidationError(
                    'Perfil não encontrado ou não pertence ao usuário.'
                )
        else:
            raise serializers.ValidationError('Header X-Relative-Id é obrigatório.')

        return super().create(validated_data)


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer completo para leitura de faturas.
    Inclui nome do cartão para exibição sem requisição adicional.
    total_amount é calculado e atualizado via Invoice.recalculate_total() (Parte 6).
    """

    # Campo de exibição read-only para evitar requisição adicional ao cartão
    credit_card_name = serializers.CharField(
        source='credit_card.name', read_only=True
    )

    class Meta:
        model = Invoice
        fields = [
            'id',
            'credit_card',
            'credit_card_name',
            'reference_month',
            'reference_year',
            'status',
            'due_date',
            'total_amount',
            'paid_at',
            'paid_via_account',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'credit_card',
            'reference_month',
            'reference_year',
            'total_amount',
            'paid_at',
            'paid_via_account',
            'created_at',
            'updated_at',
        ]
