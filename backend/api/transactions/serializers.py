from rest_framework import serializers

from backend.api.accounts.models import Account
from backend.api.credit_cards.models import CreditCard
from backend.api.relatives.models import Relative

from .models import RecurringRule, Transaction


class TransactionListSerializer(serializers.ModelSerializer):
    """
    Serializer compacto para listagem de transações.
    Expõe campos essenciais para o dashboard e extratos, sem dados aninhados pesados.
    Inclui transfer_direction para o frontend distinguir entrada/saída de transferências
    e invoice para identificar transações de cartão.
    """

    account_name = serializers.CharField(
        source='account.name', read_only=True, allow_null=True)
    category_name = serializers.CharField(
        source='category.name', read_only=True, allow_null=True)

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
            'invoice',
            'installment_number',
            'installment_total',
        ]


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializer completo para criação, edição e recuperação de transações.

    Campos especiais de escrita (não persistem no model diretamente):
    - destination_account: obrigatório ao criar uma transferência.
    - credit_card: obrigatório ao criar transação de cartão de crédito.
      A view determina a invoice correta via get_or_create_invoice().
      Com installment_total > 1 cria N transações parceladas.

    invoice é determinado automaticamente pela view — não editável pelo usuário.
    """

    account_name = serializers.CharField(
        source='account.name', read_only=True, allow_null=True)
    category_name = serializers.CharField(
        source='category.name', read_only=True, allow_null=True)
    recurring_rule_description = serializers.CharField(
        source='recurring_rule.description', read_only=True, allow_null=True
    )

    destination_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    credit_card = serializers.PrimaryKeyRelatedField(
        queryset=CreditCard.objects.all(),
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
            'invoice',
            'transfer_pair_id',
            'transfer_direction',
            'installment_group_id',
            'created_at',
            'updated_at',
            'account_name',
            'category_name',
            'recurring_rule_description',
        ]

    def validate_amount(self, value):
        """
        Garante que o valor da transação seja sempre positivo.
        """
        if value <= 0:
            raise serializers.ValidationError('O valor deve ser positivo.')
        return value

    def validate(self, data):
        """
        Validações que dependem de múltiplos campos:
        - category obrigatória para receita e despesa
        - credit_card e account mutuamente exclusivos no create
        - credit_card deve pertencer ao usuário
        - transferências não podem ser de cartão
        - installment_number não pode ser enviado pelo usuário (auto-gerado)
        - destination_account obrigatório/único para transferências novas
        - campos de parcelamento consistentes (fora do fluxo de cartão)
        """
        transaction_type = data.get('type') or (
            self.instance and self.instance.type)
        category = data.get('category') if 'category' in data else (
            self.instance and self.instance.category)
        credit_card = data.get('credit_card')

        if transaction_type in ('receita', 'despesa') and not category:
            raise serializers.ValidationError({
                'category': 'Categoria é obrigatória para receitas e despesas.'
            })

        # Validações específicas para criação de transação de cartão
        if credit_card and not self.instance:
            if transaction_type == 'transferencia':
                raise serializers.ValidationError({
                    'credit_card': 'Transferências não podem ser realizadas pelo cartão de crédito.'
                })

            if data.get('account'):
                raise serializers.ValidationError({
                    'credit_card': 'Informe apenas a conta bancária ou o cartão de crédito, não ambos.'
                })

            user = self.context['request'].user
            if not CreditCard.objects.filter(pk=credit_card.pk, user=user).exists():
                raise serializers.ValidationError({
                    'credit_card': 'Cartão não encontrado ou não pertence ao usuário.'
                })

            # installment_number é auto-gerado — não deve vir do usuário
            if data.get('installment_number') is not None:
                raise serializers.ValidationError({
                    'installment_number': (
                        'installment_number é gerado automaticamente. '
                        'Informe apenas installment_total para parcelar.'
                    )
                })

            installment_total = data.get('installment_total')
            if installment_total is not None and installment_total < 1:
                raise serializers.ValidationError({
                    'installment_total': 'O número de parcelas deve ser pelo menos 1.'
                })

        # Validações específicas para criação de transferência
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

            user = self.context['request'].user
            if not Account.objects.filter(pk=destination_account.pk, user=user).exists():
                raise serializers.ValidationError({
                    'destination_account': 'Conta de destino não encontrada ou não pertence ao usuário.'
                })

        # Valida consistência dos campos de parcelamento apenas fora do fluxo de cartão
        # (no fluxo de cartão, installment_number e installment_group_id são auto-gerados)
        if not credit_card or self.instance:
            installment_number = data.get('installment_number')
            installment_total = data.get('installment_total')
            installment_group_id = data.get('installment_group_id')

            if (installment_number is None) != (installment_total is None):
                raise serializers.ValidationError(
                    'installment_number e installment_total devem ser informados juntos.'
                )

            if installment_group_id and installment_number is None:  # pragma: no cover
                raise serializers.ValidationError(
                    'installment_number e installment_total são obrigatórios quando installment_group_id é informado.'
                )

        return data

    def create(self, validated_data):
        """
        Associa automaticamente o usuário autenticado e o perfil do header X-Relative-Id.
        destination_account e credit_card são extraídos pela view antes do save().
        """
        validated_data['user'] = self.context['request'].user

        relative_id = self.context['request'].headers.get('X-Relative-Id')
        if relative_id:
            try:
                relative = Relative.objects.get(
                    id=relative_id, user=validated_data['user'])
                validated_data['relative'] = relative
            except Relative.DoesNotExist:
                raise serializers.ValidationError(
                    'Perfil não encontrado ou não pertence ao usuário.')
        else:
            raise serializers.ValidationError(
                'Header X-Relative-Id é obrigatório.')

        return super().create(validated_data)


class RecurringRuleListSerializer(serializers.ModelSerializer):
    """
    Serializer compacto para listagem de regras de recorrência.
    """

    account_name = serializers.CharField(
        source='account.name', read_only=True, allow_null=True)
    category_name = serializers.CharField(
        source='category.name', read_only=True, allow_null=True)

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
    """

    account_name = serializers.CharField(
        source='account.name', read_only=True, allow_null=True)
    category_name = serializers.CharField(
        source='category.name', read_only=True, allow_null=True)

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
        start_date = data.get('start_date') or (
            self.instance and self.instance.start_date)

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
                relative = Relative.objects.get(
                    id=relative_id, user=validated_data['user'])
                validated_data['relative'] = relative
            except Relative.DoesNotExist:
                raise serializers.ValidationError(
                    'Perfil não encontrado ou não pertence ao usuário.')
        else:
            raise serializers.ValidationError(
                'Header X-Relative-Id é obrigatório.')

        return super().create(validated_data)
