from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

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

        return value
