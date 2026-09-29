from django.shortcuts import get_object_or_404

from ..models import Compte
from ..scoping import resolve_entreprise_id, scoping_enabled


def tenant_id(request):
    return resolve_entreprise_id(request) if scoping_enabled() else ""


def scoped_queryset(request, queryset, field="entreprise_id"):
    if not scoping_enabled():
        return queryset
    return queryset.filter(**{field: tenant_id(request)})


def scoped_comptes(request, *, actif=None):
    qs = Compte.objects.all()
    qs = scoped_queryset(request, qs)
    if actif is not None:
        qs = qs.filter(actif=actif)
    return qs


def get_scoped_compte_or_404(request, *, pk, actif=None):
    return get_object_or_404(scoped_comptes(request, actif=actif), pk=pk)
