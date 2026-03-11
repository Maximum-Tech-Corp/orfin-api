import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class RecurringRule(models.Model):
    """
    Template de regras de recorrência para geração automática de transações periódicas.
    Uma RecurringRule representa a "definição" da recorrência; as instâncias reais ficam
    na tabela Transaction com FK para esta regra.
    """

    FREQUENCY_CHOICES = [
        ('daily', 'Diário'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensal'),
        ('yearly', 'Anual'),
    ]

    TRANSACTION_TYPES = [
        ('receita', 'Receita'),
        ('despesa', 'Despesa'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recurring_rules',
        verbose_name='Usuário'
    )
    relative = models.ForeignKey(
        'api.Relative',
        on_delete=models.CASCADE,
        related_name='recurring_rules',
        verbose_name='Perfil'
    )
    # Conta associada à recorrência (null quando for transação de cartão — Parte 5)
    account = models.ForeignKey(
        'api.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_rules',
        verbose_name='Conta'
    )
    # credit_card será adicionado na Parte 5 (CreditCard + Invoice)
    category = models.ForeignKey(
        'api.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_rules',
        verbose_name='Categoria'
    )

    type = models.CharField(
        max_length=10, choices=TRANSACTION_TYPES, verbose_name='Tipo')
    frequency = models.CharField(
        max_length=10, choices=FREQUENCY_CHOICES, verbose_name='Frequência')
    # Intervalo entre ocorrências: 1 = toda semana, 2 = a cada 2 semanas, etc.
    interval = models.PositiveIntegerField(default=1, verbose_name='Intervalo')
    start_date = models.DateField(verbose_name='Data de início')
    # end_date e occurrences_count são mutuamente exclusivos — validado em clean()
    end_date = models.DateField(
        null=True, blank=True, verbose_name='Data de encerramento')
    occurrences_count = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Número de ocorrências'
    )

    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='Valor')
    description = models.CharField(max_length=255, verbose_name='Descrição')
    is_active = models.BooleanField(default=True, verbose_name='Ativo')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Valida regras de negócio da RecurringRule:
        - end_date e occurrences_count são mutuamente exclusivos
        - end_date deve ser posterior a start_date
        - amount deve ser positivo
        """
        if self.end_date and self.occurrences_count:
            raise ValidationError(
                'Informe apenas "data de encerramento" ou "número de ocorrências", não ambos.'
            )

        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': 'A data de encerramento deve ser posterior à data de início.'
            })

        if self.amount is not None:
            from decimal import Decimal, InvalidOperation
            try:
                if Decimal(str(self.amount)) <= 0:
                    raise ValidationError(
                        {'amount': 'O valor deve ser positivo.'})
            except InvalidOperation:
                pass  # Validação de formato fica a cargo do Django/serializer

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Previne exclusão física de regras de recorrência.
        Use soft_delete() para desativar.
        """
        raise NotImplementedError(
            'Não é permitido deletar regras de recorrência diretamente.')

    def soft_delete(self):
        """
        Desativa a regra de recorrência ao invés de deletá-la.
        """
        self.is_active = False
        self.save()

    def __str__(self):
        return f'{self.description} ({self.get_frequency_display()} - {self.get_type_display()})'

    class Meta:
        db_table = 'recurring_rule'
        verbose_name = 'Regra de Recorrência'
        verbose_name_plural = 'Regras de Recorrência'
        ordering = ['-created_at']


class Transaction(models.Model):
    """
    Entidade central do sistema financeiro. Comporta receitas, despesas e transferências
    em uma única tabela. O campo `type` determina a direção do fluxo de caixa.

    Deleção: hard delete — o usuário pode apagar transações permanentemente.
    A lógica de reversão de saldo antes do delete é responsabilidade da view (Parte 2).

    Constraints importantes:
    - account XOR invoice: nunca os dois preenchidos ao mesmo tempo (invoice será adicionado na Parte 5)
    - category é obrigatória para receita e despesa; opcional para transferencia
    - amount é sempre positivo; o tipo determina a direção
    """

    TRANSACTION_TYPES = [
        ('receita', 'Receita'),
        ('despesa', 'Despesa'),
        ('transferencia', 'Transferência'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name='Usuário'
    )
    relative = models.ForeignKey(
        'api.Relative',
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name='Perfil'
    )
    # Null quando for transação de cartão de crédito (invoice preenchido) — constraint Parte 5
    account = models.ForeignKey(
        'api.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name='Conta'
    )
    # invoice (FK → Invoice) será adicionado na Parte 5 (CreditCard + Invoice)
    category = models.ForeignKey(
        'api.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name='Categoria'
    )
    # Regra de recorrência que originou esta transação (null = lançamento avulso)
    recurring_rule = models.ForeignKey(
        RecurringRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name='Regra de Recorrência'
    )

    # UUID compartilhado entre dois registros de transferência (origem e destino)
    transfer_pair_id = models.UUIDField(
        null=True, blank=True, verbose_name='ID do Par de Transferência'
    )
    # UUID compartilhado entre parcelas de uma compra parcelada no cartão
    installment_group_id = models.UUIDField(
        null=True, blank=True, verbose_name='ID do Grupo de Parcelas'
    )
    installment_number = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Número da Parcela'
    )
    installment_total = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Total de Parcelas'
    )

    type = models.CharField(
        max_length=15, choices=TRANSACTION_TYPES, verbose_name='Tipo')
    # Sempre positivo — o tipo (receita/despesa/transferencia) determina a direção do fluxo
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='Valor')
    description = models.CharField(max_length=255, verbose_name='Descrição')
    # Campo livre para anotações adicionais sobre a transação (ex: número NF, referência, lembrete)
    notes = models.TextField(max_length=500, null=True,
                             blank=True, verbose_name='Observação')
    # Data de competência (quando ocorreu/ocorrerá a transação)
    date = models.DateField(verbose_name='Data')
    # False = lançamento previsto/agendado; True = confirmado/realizado
    is_paid = models.BooleanField(default=False, verbose_name='Pago')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Valida regras de negócio da Transaction:
        - amount deve ser positivo
        - category é obrigatória para receita e despesa
        - campos de parcelamento devem ser consistentes entre si
        """
        if self.amount is not None:
            from decimal import Decimal, InvalidOperation
            try:
                if Decimal(str(self.amount)) <= 0:
                    raise ValidationError(
                        {'amount': 'O valor da transação deve ser positivo.'})
            except InvalidOperation:
                pass  # Validação de formato fica a cargo do Django/serializer

        # Categoria obrigatória para receita e despesa (opcional para transferencia)
        if self.type in ('receita', 'despesa') and not self.category_id:
            raise ValidationError({
                'category': 'Categoria é obrigatória para receitas e despesas.'
            })

        # Valida consistência dos campos de parcelamento
        has_installment_number = self.installment_number is not None
        has_installment_total = self.installment_total is not None
        if has_installment_number != has_installment_total:
            raise ValidationError(
                'installment_number e installment_total devem ser informados juntos.'
            )

        if self.installment_group_id and not has_installment_number:
            raise ValidationError(
                'installment_number e installment_total são obrigatórios quando installment_group_id é informado.'
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.description} — R$ {self.amount} ({self.get_type_display()})'

    class Meta:
        db_table = 'transaction'
        verbose_name = 'Transação'
        verbose_name_plural = 'Transações'
        ordering = ['-date', '-created_at']
        indexes = [
            # Índice principal para queries do dashboard (filtro por período e perfil)
            models.Index(
                fields=['user', 'relative', 'date'],
                name='idx_transaction_period'
            ),
            # Índice para extrato de conta
            models.Index(fields=['account', 'date'],
                         name='idx_transaction_account'),
            # Índice para relatórios por categoria
            models.Index(fields=['category', 'date'],
                         name='idx_transaction_category'),
            # Índice para gerenciamento de recorrências
            models.Index(
                fields=['recurring_rule', 'date'], name='idx_transaction_recurring'
            ),
            # Índice para gerenciamento de parcelamentos
            models.Index(
                fields=['installment_group_id'], name='idx_transaction_installment'
            ),
        ]
