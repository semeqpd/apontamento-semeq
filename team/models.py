from django.db import models
from uuid import uuid4
from django.core.validators import MinLengthValidator

# Create your models here.

class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(unique=True,
                            blank=False, 
                            null=False, 
                            validators=[MinLengthValidator(2)],
                            verbose_name='Nome completo')
    description = models.CharField(blank=False, 
                                null=False, 
                                validators=[MinLengthValidator(5)],
                                verbose_name='Descrição')

    active = models.BooleanField(verbose_name='Ativo')
    create_at = models.DateField(verbose_name='Data criada')
    updated_at = models.DateField(verbose_name='Última alteração')

    