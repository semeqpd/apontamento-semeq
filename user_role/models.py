from django.db import models
from role.models import Role
from uuid import uuid4

class User_Role(models.Model):
        id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
        user_id = models.ForeignKey('user.User', on_delete=models.CASCADE, related_name='user', verbose_name='user_id')
        role_id = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role', verbose_name='role_id')                 
        created_at = models.DateField(verbose_name="Data criado")