"""
Custom authentication backends for SEMEQ Portal.
Supports authentication via email instead of username.
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Autenticação via email (case-insensitive).
    
    Permite login usando email + senha em vez de username + senha.
    Mantém compatibilidade com username para usuários existentes.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
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
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None
    
    def user_can_authenticate(self, user):
        """
        Verifica se o usuário pode se autenticar.
        Requer: is_active=True e perfil.ativo=True
        """
        is_active = getattr(user, 'is_active', False)
        perfil_ativo = False
        if hasattr(user, 'perfil'):
            perfil_ativo = getattr(user.perfil, 'ativo', False)
        
        return is_active and perfil_ativo
    
    def get_user(self, user_id):
        try:
            user = User.objects.select_related('perfil').get(pk=user_id)
        except User.DoesNotExist:
            return None
        
        if self.user_can_authenticate(user):
            return user
        return None