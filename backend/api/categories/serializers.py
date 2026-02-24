from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['user', 'relative']  # Usuário e relative são definidos automaticamente

    def create(self, validated_data):
        """
        Cria uma nova categoria associando automaticamente ao usuário logado e relative do header.
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

    def validate_color(self, value):
        if not value.startswith('#') or len(value) != 7:
            raise serializers.ValidationError(
                "Cor deve estar no formato hexadecimal #RRGGBB."
            )

        # Verifica se os caracteres após # são hexadecimais válidos
        hex_chars = value[1:]
        if not all(c in '0123456789ABCDEFabcdef' for c in hex_chars):
            raise serializers.ValidationError(
                "Cor deve conter apenas caracteres hexadecimais válidos."
            )

        return value.upper()  # Padroniza para maiúsculas

    def validate_subcategory(self, value):
        """
        Valida se a subcategoria não cria referência circular.
        Impede que uma categoria seja subcategoria de si mesma.
        """
        if value and self.instance:
            # Verifica se está tentando criar referência circular
            if value.id == self.instance.id:
                raise serializers.ValidationError(
                    "Uma categoria não pode ser subcategoria de si mesma."
                )

        # Valida se a subcategoria pertence ao mesmo usuário e perfil
        # (também validado no modelo, sendo uma boa prática validar aqui também)
        if value and hasattr(self, 'context') and 'request' in self.context:
            user = self.context['request'].user
            relative_id = self.context['request'].headers.get('X-Relative-Id')

            if value.user != user:
                raise serializers.ValidationError(
                    "A categoria pai deve pertencer ao mesmo usuário."
                )

            if relative_id and str(value.relative.id) != relative_id:
                raise serializers.ValidationError(
                    "A categoria pai deve pertencer ao mesmo perfil."
                )

        return value
