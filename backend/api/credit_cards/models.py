import calendar
import datetime
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CreditCard(models.Model):
    """
    Cartão de crédito do usuário, vinculado a um Relative.
    Armazena as configurações de fechamento (closing_day) e vencimento (due_day)
    que determinam a qual fatura cada transação pertence.
    Soft delete via is_archived — nunca excluir fisicamente.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='credit_cards',
        verbose_name='Usuário',
    )
    relative = models.ForeignKey(
        'api.Relative',
        on_delete=models.CASCADE,
        related_name='credit_cards',
        verbose_name='Perfil',
    )

    name = models.CharField(max_length=50, verbose_name='Nome')
    # Cor em formato hexadecimal (#RRGGBB) — validação de formato feita no serializer
    color = models.CharField(max_length=7, verbose_name='Cor')
    limit = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Limite')
    # Dia do mês em que a fatura fecha (1-28 para garantir validade em todos os meses)
    closing_day = models.PositiveIntegerField(verbose_name='Dia de fechamento')
    # Dia do mês do vencimento da fatura (1-28)
    due_day = models.PositiveIntegerField(verbose_name='Dia de vencimento')
    is_archived = models.BooleanField(default=False, verbose_name='Arquivado')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Valida regras de negócio do CreditCard:
        - closing_day e due_day devem estar entre 1 e 28
        - limit deve ser positivo
        """
        if self.closing_day is not None and not 1 <= self.closing_day <= 28:
            raise ValidationError({
                'closing_day': 'O dia de fechamento deve estar entre 1 e 28.'
            })

        if self.due_day is not None and not 1 <= self.due_day <= 28:
            raise ValidationError({
                'due_day': 'O dia de vencimento deve estar entre 1 e 28.'
            })

        if self.limit is not None and self.limit <= 0:
            raise ValidationError({
                'limit': 'O limite deve ser positivo.'
            })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Impede a exclusão física de cartões de crédito.
        Use soft_delete() para arquivá-los.
        """
        raise NotImplementedError(
            'Não é permitido deletar cartões de crédito. Use o arquivamento.'
        )

    def soft_delete(self):
        """
        Arquiva o cartão ao invés de deletá-lo.
        Preserva o histórico de faturas e transações vinculadas.
        """
        self.is_archived = True
        self.save()

    def __str__(self):
        return f'{self.name} (fechamento: dia {self.closing_day})'

    class Meta:
        db_table = 'credit_card'
        verbose_name = 'Cartão de Crédito'
        verbose_name_plural = 'Cartões de Crédito'
        ordering = ['-created_at']
        # Nome do cartão deve ser único por usuário e perfil
        unique_together = [('user', 'relative', 'name')]


class Invoice(models.Model):
    """
    Fatura mensal de um cartão de crédito.
    Gerada automaticamente ao criar transações de cartão via get_or_create_invoice().
    total_amount é recalculado via recalculate_total() a cada alteração de transações.
    Status é atualizado de forma lazy (update_status()) ao consultar a fatura.

    Deleção: não permitida — faturas são registros históricos imutáveis.
    """

    STATUS_CHOICES = [
        ('aberta', 'Aberta'),
        ('fechada', 'Fechada'),
        ('paga', 'Paga'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    credit_card = models.ForeignKey(
        CreditCard,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name='Cartão de Crédito',
    )
    reference_month = models.PositiveIntegerField(verbose_name='Mês de referência')
    reference_year = models.PositiveIntegerField(verbose_name='Ano de referência')
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='aberta',
        verbose_name='Status',
    )
    due_date = models.DateField(verbose_name='Data de vencimento')
    # Calculado via recalculate_total() — soma das transações da fatura
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='Valor total',
    )
    # Preenchido apenas ao confirmar pagamento (Parte 7)
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Pago em')
    # Conta debitada no pagamento — preenchida apenas ao confirmar (Parte 7)
    paid_via_account = models.ForeignKey(
        'api.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paid_invoices',
        verbose_name='Conta de pagamento',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def update_status(self):
        """
        Fecha a fatura automaticamente se o dia de fechamento já passou.
        Abordagem lazy: chamada ao consultar/listar faturas, sem job periódico.
        Faturas pagas nunca são reabertas ou fechadas por esta lógica.
        """
        if self.status != 'aberta':
            return

        closing_date = datetime.date(
            self.reference_year,
            self.reference_month,
            self.credit_card.closing_day,
        )
        if datetime.date.today() > closing_date:
            self.status = 'fechada'
            self.save(update_fields=['status', 'updated_at'])

    def recalculate_total(self):
        """
        Recalcula total_amount como soma das transações vinculadas a esta fatura.
        Chamado sempre que uma transação de cartão é criada, editada ou removida (Parte 6).
        Usa import local para evitar importação circular com transactions.models.
        """
        from backend.api.transactions.models import Transaction
        total = (
            Transaction.objects
            .filter(invoice=self)
            .aggregate(total=models.Sum('amount'))['total']
        ) or Decimal('0')
        self.total_amount = total
        self.save(update_fields=['total_amount', 'updated_at'])

    def __str__(self):
        return (
            f'Fatura {self.reference_month:02d}/{self.reference_year}'
            f' — {self.credit_card.name} ({self.status})'
        )

    class Meta:
        db_table = 'invoice'
        verbose_name = 'Fatura'
        verbose_name_plural = 'Faturas'
        ordering = ['-reference_year', '-reference_month']
        # Garante que cada cartão tenha no máximo uma fatura por mês/ano
        unique_together = [('credit_card', 'reference_month', 'reference_year')]


# ---------------------------------------------------------------------------
# Helper de geração automática de fatura
# ---------------------------------------------------------------------------

def get_or_create_invoice(credit_card: CreditCard, transaction_date: datetime.date) -> Invoice:
    """
    Retorna a Invoice correta para um cartão dado a data da transação.

    A fatura de referência é determinada pelo closing_day do cartão:
    - Se transaction_date.day <= closing_day → fatura do mês corrente
    - Se transaction_date.day > closing_day → fatura do próximo mês

    Cria a fatura automaticamente se ainda não existir.
    O due_day é ajustado para o último dia do mês quando necessário (ex: dia 31 em fevereiro).
    """
    if transaction_date.day <= credit_card.closing_day:
        ref_month = transaction_date.month
        ref_year = transaction_date.year
    else:
        # Transação após o fechamento vai para a fatura do próximo mês
        if transaction_date.month == 12:
            ref_month = 1
            ref_year = transaction_date.year + 1
        else:
            ref_month = transaction_date.month + 1
            ref_year = transaction_date.year

    # Ajusta o due_day para o último dia do mês de referência se necessário
    due_day = min(credit_card.due_day, calendar.monthrange(ref_year, ref_month)[1])
    due_date = datetime.date(ref_year, ref_month, due_day)

    invoice, _ = Invoice.objects.get_or_create(
        credit_card=credit_card,
        reference_month=ref_month,
        reference_year=ref_year,
        defaults={
            'status': 'aberta',
            'due_date': due_date,
            'total_amount': Decimal('0'),
        },
    )
    return invoice
