from django.db import models
from uuid import uuid4

class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(blank=False,
                            null=False,
                            unique=True,
                            verbose_name='Nome')
    description = models.CharField(blank=False,
                                null=False,
                                unique=True,
                                verbose_name='Descrição')
    create_at = models.DateField(verbose_name='Data criada')
    updated_at = models.DateField(verbose_name='Última alteração')
    