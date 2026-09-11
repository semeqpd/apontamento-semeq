"""
Custom authentication backends for SEMEQ Portal.
Supports authentication via email instead of username.
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


def normalize_email(email: str) -> str:
    """Normalize email: strip whitespace and lowercase."""
    return email.strip().lower() if email else ''


class EmailBackend(ModelBackend):
    """
    Autenticação via email (case-insensitive).
    
    Permite login usando email + senha em vez de username + senha.
    Mantém compatibilidade com username para usuários existentes.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Normalize username/email
        if username:
            username = normalize_email(username)
        
        # Se username contém @, trata como email
        if username and '@' in username:
            try:
                user = User.objects.get(email__iexact=username)
            except User.DoesNotExist:
                # Run the default password hasher once to reduce timing difference
                User().set_password(password)
                return None
            except User.MultipleObjectsReturned:
                return None
        else:
            # Fallback: tenta buscar por username (compatibilidade)
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                User().set_password(password)
                return None
            except User.MultipleObjectsReturned:
                return None
        
        # Verifica senha
        if user.check_password(password):
            # Check if user can authenticate
            is_active = getattr(user, 'is_active', False)
            
            if not is_active:
                # User exists but is inactive
                raise ValidationError(
                    'Sua conta está desativada.',
                    code='inactive_user'
                )
            return user
        
        return None
    
    def get_user(self, user_id):
        try:
            user = User.objects.select_related('perfil').get(pk=user_id)
        except User.DoesNotExist:
            return None
        
        if self.user_can_authenticate(user):
            return user
        return None