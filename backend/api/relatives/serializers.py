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

    def validate_name(self, value):
        """
        Verifica se o usuário já possui um perfil com o mesmo nome.
        """
        user = self.context['request'].user
        queryset = Relative.objects.filter(user=user, name=value)

        # Em caso de update, exclui o próprio registro da verificação
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                'Você já possui um perfil com este nome.')

        return value

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
