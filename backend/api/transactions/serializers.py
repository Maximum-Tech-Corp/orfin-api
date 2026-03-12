from rest_framework import serializers

from backend.api.accounts.models import Account
from backend.api.relatives.models import Relative

from .models import RecurringRule, Transaction


class TransactionListSerializer(serializers.ModelSerializer):
    """
    Serializer compacto para listagem de transações.
    Expõe campos essenciais para o dashboard e extratos, sem dados aninhados pesados.
    Inclui transfer_direction para o frontend distinguir entrada/saída de transferências.
    """

    # Campos de exibição para evitar requisições adicionais na lista
    account_name = serializers.CharField(source='account.name', read_only=True, allow_null=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)

    class Meta:
        model = Transaction
        fields = [
            'id',
            'type',
            'transfer_direction',
            'amount',
            'description',
            'date',
            'is_paid',
            'account',
            'account_name',
            'category',
            'category_name',
        ]


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializer completo para criação, edição e recuperação de transações.

    Campo especial de escrita (não persiste no model diretamente):
    - destination_account: obrigatório ao criar uma transferência; indica a conta de destino.
      A view usa este campo para criar o par de transações atomicamente.
    """

    # Campos de exibição read-only para contexto sem requisições extras
    account_name = serializers.CharField(source='account.name', read_only=True, allow_null=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    recurring_rule_description = serializers.CharField(
        source='recurring_rule.description', read_only=True, allow_null=True
    )

    # Campo write-only usado apenas na criação de transferências
    destination_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = [
            'user',
            'relative',
            'transfer_pair_id',
            'transfer_direction',
            'created_at',
            'updated_at',
            'account_name',
            'category_name',
            'recurring_rule_description',
        ]

    def validate_amount(self, value):
        """
        Garante que o valor da transação seja sempre positivo.
        A direção do fluxo é determinada pelo campo `type`.
        """
        if value <= 0:
            raise serializers.ValidationError('O valor deve ser positivo.')
        return value

    def validate(self, data):
        """
        Validações que dependem de múltiplos campos:
        - category obrigatória para receita e despesa
        - campos de parcelamento consistentes
        - destination_account obrigatório e diferente da origem para transferências novas
        - destination_account deve pertencer ao mesmo usuário
        """
        transaction_type = data.get('type') or (self.instance and self.instance.type)
        category = data.get('category') if 'category' in data else (self.instance and self.instance.category)

        if transaction_type in ('receita', 'despesa') and not category:
            raise serializers.ValidationError({
                'category': 'Categoria é obrigatória para receitas e despesas.'
            })

        # Validações específicas para criação de transferência (não se aplica ao update)
        if transaction_type == 'transferencia' and not self.instance:
            destination_account = data.get('destination_account')
            if not destination_account:
                raise serializers.ValidationError({
                    'destination_account': 'Conta de destino é obrigatória para transferências.'
                })

            origin_account = data.get('account')
            if origin_account and origin_account == destination_account:
                raise serializers.ValidationError({
                    'destination_account': 'Conta de destino deve ser diferente da conta de origem.'
                })

            # Garante que a conta de destino pertence ao usuário autenticado
            user = self.context['request'].user
            if not Account.objects.filter(pk=destination_account.pk, user=user).exists():
                raise serializers.ValidationError({
                    'destination_account': 'Conta de destino não encontrada ou não pertence ao usuário.'
                })

        # Valida consistência dos campos de parcelamento
        installment_number = data.get('installment_number')
        installment_total = data.get('installment_total')
        installment_group_id = data.get('installment_group_id')

        if (installment_number is None) != (installment_total is None):
            raise serializers.ValidationError(
                'installment_number e installment_total devem ser informados juntos.'
            )

        if installment_group_id and installment_number is None:
            raise serializers.ValidationError(
                'installment_number e installment_total são obrigatórios quando installment_group_id é informado.'
            )

        return data

    def create(self, validated_data):
        """
        Associa automaticamente o usuário autenticado e o perfil do header X-Relative-Id.
        destination_account é extraído pela view antes de chamar save() — não chega aqui.
        """
        validated_data['user'] = self.context['request'].user

        relative_id = self.context['request'].headers.get('X-Relative-Id')
        if relative_id:
            try:
                relative = Relative.objects.get(id=relative_id, user=validated_data['user'])
                validated_data['relative'] = relative
            except Relative.DoesNotExist:
                raise serializers.ValidationError('Perfil não encontrado ou não pertence ao usuário.')
        else:
            raise serializers.ValidationError('Header X-Relative-Id é obrigatório.')

        return super().create(validated_data)


class RecurringRuleListSerializer(serializers.ModelSerializer):
    """
    Serializer compacto para listagem de regras de recorrência.
    """

    account_name = serializers.CharField(source='account.name', read_only=True, allow_null=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)

    class Meta:
        model = RecurringRule
        fields = [
            'id',
            'type',
            'frequency',
            'interval',
            'amount',
            'description',
            'start_date',
            'end_date',
            'is_active',
            'account',
            'account_name',
            'category',
            'category_name',
        ]


class RecurringRuleSerializer(serializers.ModelSerializer):
    """
    Serializer completo para criação e edição de regras de recorrência.
    A lógica de geração das instâncias de Transaction (Parte 4) será feita nas views.
    """

    account_name = serializers.CharField(source='account.name', read_only=True, allow_null=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)

    class Meta:
        model = RecurringRule
        fields = '__all__'
        read_only_fields = ['user', 'relative', 'created_at', 'updated_at']

    def validate_amount(self, value):
        """
        Garante que o valor da regra de recorrência seja positivo.
        """
        if value <= 0:
            raise serializers.ValidationError('O valor deve ser positivo.')
        return value

    def validate(self, data):
        """
        Valida que end_date e occurrences_count não sejam informados simultaneamente,
        e que end_date seja posterior a start_date.
        """
        end_date = data.get('end_date')
        occurrences_count = data.get('occurrences_count')
        start_date = data.get('start_date') or (self.instance and self.instance.start_date)

        if end_date and occurrences_count:
            raise serializers.ValidationError(
                'Informe apenas "data de encerramento" ou "número de ocorrências", não ambos.'
            )

        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'A data de encerramento deve ser posterior à data de início.'
            })

        return data

    def create(self, validated_data):
        """
        Associa automaticamente o usuário autenticado e o perfil do header X-Relative-Id.
        """
        validated_data['user'] = self.context['request'].user

        relative_id = self.context['request'].headers.get('X-Relative-Id')
        if relative_id:
            try:
                relative = Relative.objects.get(id=relative_id, user=validated_data['user'])
                validated_data['relative'] = relative
            except Relative.DoesNotExist:
                raise serializers.ValidationError('Perfil não encontrado ou não pertence ao usuário.')
        else:
            raise serializers.ValidationError('Header X-Relative-Id é obrigatório.')

        return super().create(validated_data)
