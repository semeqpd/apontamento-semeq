"""
Centralized authorization policies for SEMEQ Portal.
All permission checks should go through this module.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model

User = get_user_model()


class PermissionDenied(Exception):
    """Raised when a permission check fails."""
    pass


def get_user_perfil(user):
    """Safely get user's perfil, return None if not exists."""
    return getattr(user, 'perfil', None)


def is_admin(user) -> bool:
    """Check if user is Administrator (admin role or superuser)."""
    perfil = get_user_perfil(user)
    return perfil is not None and (perfil.role == 'admin' or user.is_superuser)


def is_gestor(user) -> bool:
    """Check if user is Gestor or above."""
    perfil = get_user_perfil(user)
    return perfil is not None and perfil.role in ('admin', 'gestor') or user.is_superuser


def is_lider(user) -> bool:
    """Check if user is Líder or above."""
    perfil = get_user_perfil(user)
    return perfil is not None and perfil.role in ('admin', 'gestor', 'lider') or user.is_superuser


def is_colaborador(user) -> bool:
    """Check if user is Colaborador."""
    perfil = get_user_perfil(user)
    return perfil is not None and perfil.role == 'colaborador'


def get_user_role(user) -> str | None:
    """Get user's role string."""
    perfil = get_user_perfil(user)
    return perfil.role if perfil else None


def get_user_equipe(user):
    """Get user's equipe."""
    perfil = get_user_perfil(user)
    return perfil.equipe if perfil else None


# =====================================================================
# APONTAMENTO PERMISSIONS
# =====================================================================

def can_view_apontamento(user, apontamento) -> bool:
    """
    Check if user can view an apontamento.
    
    Rules:
    - Admin/Gestor: all apontamentos
    - Líder: apontamentos da própria equipe (apontamento.equipe == user.equipe)
    - Colaborador: apenas próprios (apontamento.responsavel == user OR apontamento.criado_por == user)
    """
    if not user.is_authenticated:
        return False
    
    perfil = get_user_perfil(user)
    if not perfil or not perfil.ativo:
        return False
    
    if is_admin(user) or is_gestor(user):
        return True
    
    if is_lider(user):
        # Líder vê apontamentos da sua equipe
        return apontamento.equipe_id == perfil.equipe_id
    
    # Colaborador vê apenas onde é responsavel OU criou
    return apontamento.responsavel_id == user.id or apontamento.criado_por_id == user.id


def can_create_apontamento(user) -> bool:
    """Check if user can create apontamentos. All authenticated active users can."""
    if not user.is_authenticated:
        return False
    perfil = get_user_perfil(user)
    return perfil is not None and perfil.ativo


def can_edit_apontamento(user, apontamento) -> bool:
    """
    Check if user can edit an apontamento.
    
    Rules:
    - ALL users (Admin, Gestor, Líder, Colaborador): can edit ONLY their own
      (where they are the responsavel OR created it)
    """
    if not user.is_authenticated:
        return False
    
    perfil = get_user_perfil(user)
    if not perfil or not perfil.ativo:
        return False
    
    # Todos editam apenas seus próprios apontamentos
    return apontamento.responsavel_id == user.id or apontamento.criado_por_id == user.id


def can_delete_apontamento(user, apontamento) -> bool:
    """
    Check if user can delete an apontamento.
    
    Rules (same as edit):
    - Admin/Gestor: can delete any
    - Líder: can delete ONLY own (criado_por == user)
    - Colaborador: can delete ONLY own (criado_por == user)
    """
    return can_edit_apontamento(user, apontamento)


def filter_apontamentos_queryset(user, qs):
    """
    Filter apontamentos queryset based on user's permissions.
    Use this in list views instead of manual filtering.
    """
    if not user.is_authenticated:
        return qs.none()
    
    perfil = get_user_perfil(user)
    if not perfil or not perfil.ativo:
        return qs.none()
    
    if is_admin(user) or is_gestor(user):
        return qs  # all
    
    if is_lider(user):
        # Líder vê apontamentos da equipe (via equipe do apontamento)
        return qs.filter(equipe=perfil.equipe)
    
    # Colaborador vê apenas onde é responsavel
    return qs.filter(responsavel=user)


def filter_apontamentostempo_queryset(user, qs):
    """
    Filter ApontamentoTempo queryset based on user's permissions.
    """
    if not user.is_authenticated:
        return qs.none()
    
    perfil = get_user_perfil(user)
    if not perfil or not perfil.ativo:
        return qs.none()
    
    if is_admin(user) or is_gestor(user):
        return qs
    
    if is_lider(user):
        # Líder vê apontamentos de tempo da equipe (via apontamento.equipe)
        return qs.filter(apontamento__equipe=perfil.equipe)
    
    # Colaborador vê apenas onde é responsavel
    return qs.filter(responsavel=user)


# =====================================================================
# USER MANAGEMENT PERMISSIONS
# =====================================================================

def can_manage_users(user) -> bool:
    """Check if user can manage (create/edit/delete) other users. Admin/Gestor only."""
    return is_admin(user) or is_gestor(user)


def can_view_user(user, target_user) -> bool:
    """
    Check if user can view another user.
    
    - Admin/Gestor: all users
    - Líder: users in same equipe
    - Colaborador: only self
    """
    if not user.is_authenticated:
        return False
    
    if user == target_user:
        return True
    
    perfil = get_user_perfil(user)
    if not perfil or not perfil.ativo:
        return False
    
    if is_admin(user) or is_gestor(user):
        return True
    
    if is_lider(user):
        target_perfil = get_user_perfil(target_user)
        return target_perfil is not None and target_perfil.equipe_id == perfil.equipe_id
    
    return False


def can_edit_user(user, target_user) -> bool:
    """
    Check if user can edit another user.
    
    - Admin: can edit anyone
    - Gestor: can edit anyone EXCEPT other admins/superusers
    - Líder: can edit users in same equipe (but not promote to admin/gestor)
    - Colaborador: cannot edit anyone
    """
    if not user.is_authenticated:
        return False
    
    if user == target_user:
        return False  # Users cannot edit themselves via admin interface
    
    perfil = get_user_perfil(user)
    if not perfil or not perfil.ativo:
        return False
    
    target_perfil = get_user_perfil(target_user)
    
    if is_admin(user):
        return True
    
    if is_gestor(user):
        # Gestor cannot edit admins/superusers
        if target_user.is_superuser or (target_perfil and target_perfil.role == 'admin'):
            return False
        return True
    
    if is_lider(user):
        # Líder can edit team members but not promote to admin/gestor
        if target_perfil and target_perfil.equipe_id == perfil.equipe_id:
            return True
    
    return False


def can_delete_user(user, target_user) -> bool:
    """
    Check if user can delete another user.
    
    Same rules as can_edit_user.
    """
    return can_edit_user(user, target_user)


def can_promote_to_role(user, target_role: str) -> bool:
    """
    Check if user can promote someone to a specific role.
    
    - Admin: can promote to any role
    - Gestor: can promote to lider, colaborador (NOT admin/gestor)
    - Líder: cannot promote
    - Colaborador: cannot promote
    """
    if not user.is_authenticated:
        return False
    
    perfil = get_user_perfil(user)
    if not perfil or not perfil.ativo:
        return False
    
    if is_admin(user):
        return True
    
    if is_gestor(user):
        return target_role in ('lider', 'colaborador')
    
    return False


def filter_users_queryset(user, qs):
    """
    Filter users queryset based on user's permissions.
    """
    if not user.is_authenticated:
        return qs.none()
    
    perfil = get_user_perfil(user)
    if not perfil or not perfil.ativo:
        return qs.none()
    
    if is_admin(user) or is_gestor(user):
        return qs.filter(perfil__ativo=True)
    
    if is_lider(user):
        return qs.filter(perfil__ativo=True, perfil__equipe=perfil.equipe)
    
    return qs.filter(id=user.id)


# =====================================================================
# EQUIPE PERMISSIONS
# =====================================================================

def can_manage_equipes(user) -> bool:
    """Check if user can manage equipes. Admin/Gestor only."""
    return is_admin(user) or is_gestor(user)


# =====================================================================
# HELPER: Check permission and raise if denied
# =====================================================================

def check_permission(condition: bool, message: str = "Sem permissão para esta ação."):
    """Raise PermissionDenied if condition is False."""
    if not condition:
        raise PermissionDenied(message)