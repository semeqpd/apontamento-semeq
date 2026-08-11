from django.db import models
from team.models import Team
from django.core.validators import MinLengthValidator
from uuid import uuid4

# Create your models here.
class User(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    fullname = models.CharField(max_length=255, 
                            blank=False, 
                            null=False, 
                            validators=[MinLengthValidator(5)],
                            verbose_name='Nome completo')
    email = models.EmailField(unique=True,
                            blank=False,
                            null=False)
    password_hash = models.CharField(max_length=255, 
                            blank=False, 
                            null=False, 
                            validators=[MinLengthValidator(8)],
                            verbose_name='Senha')
    active = models.BooleanField(verbose_name='Ativo')
    last_login = models.DateField(verbose_name='Último Login')
    create_at = models.DateField(verbose_name='Data criada')
    updated_at = models.DateField(verbose_name='Última alteração')
    team_id = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team', verbose_name='team_id')

    def __str__(self):
        return self.fullname