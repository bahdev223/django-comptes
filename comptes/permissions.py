"""
Permissions fines pour le module comptes.

Permissions definies:
    - comptes.create_compte  : Creer un compte
    - comptes.view_compte    : Voir un compte
    - comptes.change_compte  : Modifier un compte
    - comptes.delete_compte  : Supprimer un compte
    - comptes.encaisser      : Encaisser un mouvement
    - comptes.decaisser      : Decaisser un mouvement
    - comptes.transferer     : Transferer entre comptes
    - comptes.cloturer       : Cloturer un journal / compte
    - comptes.rapprocher     : Rapprocher un relevé bancaire
    - comptes.annuler        : Annuler un mouvement
    - comptes.view_all       : Voir tous les comptes (lecture seule)
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from rest_framework.permissions import BasePermission

from .models import Compte


def get_all_comptes_permissions():
    """Retourne les permissions personnalisees du module comptes."""
    content_type = ContentType.objects.get_for_model(Compte)
    return Permission.objects.filter(
        Q(content_type=content_type) & Q(codename__startswith="comptes_")
    )


def has_comptes_permission(user, permission_codename):
    """Verifie si un utilisateur a une permission specifique du module."""
    if user.is_superuser or user.is_staff:
        return True
    return user.user_permissions.filter(codename=permission_codename).exists() or (
        user.groups.filter(permissions__codename=permission_codename).exists()
    )


def require_comptes_permission(user, permission_codename):
    """Protège les services, même lorsqu'ils sont appelés hors de l'API.

    ``user=None`` est réservé aux tâches système explicitement déclenchées par
    l'application hôte (migration, import contrôlé, etc.).
    """
    if user is not None and not has_comptes_permission(user, permission_codename):
        raise PermissionDenied(f"Permission comptes.{permission_codename} requise.")


class ComptesPermission(BasePermission):
    """Applique les permissions Django, y compris aux actions métier DRF."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        codename = getattr(view, "permission_actions", {}).get(view.action)
        if codename is None:
            model = view.get_queryset().model
            action = "view" if request.method in ("GET", "HEAD", "OPTIONS") else {
                "POST": "add", "PUT": "change", "PATCH": "change", "DELETE": "delete",
            }.get(request.method)
            codename = f"{action}_{model._meta.model_name}" if action else None

        return codename is not None and has_comptes_permission(request.user, codename)
