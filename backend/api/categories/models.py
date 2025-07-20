from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7)  # Formato hex: #RRGGBB
    icon = models.CharField(max_length=20)
    is_archived = models.BooleanField(default=False)
    # Self-referencing para criar hierarquia de categorias
    subcategory = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='parent_categories'
    )

    def clean(self):
        """
        Valida se já existe categoria com mesmo nome e mesma subcategoria.
        Validação também mantem o nível máximo de subcategorias em 1.
        """
        existing = Category.objects.filter(
            name=self.name,
            subcategory=self.subcategory
        )

        if self.pk:  # Se for update, exclui o próprio registro da validação
            existing = existing.exclude(pk=self.pk)

        if existing.exists():
            raise ValidationError({
                'name': 'Já existe este nome de categoria. Use outro nome ou escolha outra categoria pai.'
            })

        if self.subcategory and self.subcategory.subcategory:
            raise ValidationError({
                'subcategory': 'Não é permitido ter mais de um nível de subcategoria.'
            })

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Previne exclusão física de categorias. 
        Na view Destroy, arquivamos ao invés de deleta-las.
        """
        raise NotImplementedError("Não é permitido deletar categorias.")

    def __str__(self):
        if self.subcategory:
            hierarchy = []
            parent = self.subcategory
            while parent:
                hierarchy.append(parent.name)
                parent = parent.subcategory
            hierarchy.reverse()
            hierarchy.append(self.name)
            return " > ".join(hierarchy)
        return self.name

    class Meta:
        db_table = 'category'
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        # Garante que não haja categorias com nomes duplicados no mesmo nível
        unique_together = ['name', 'subcategory']
