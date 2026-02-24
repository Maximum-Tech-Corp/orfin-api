from rest_framework import serializers

from .models import Relative


class RelativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relative
        fields = [
            'id',
            'name',
            'image_num',
            'is_archived',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        """
        Cria um novo perfil associando automaticamente ao usuário logado.
        """
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class RelativeListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listagem de perfis.
    """

    class Meta:
        model = Relative
        fields = [
            'id',
            'name',
            'image_num',
            'is_archived'
        ]
