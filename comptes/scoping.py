from importlib import import_module

from django.core.exceptions import PermissionDenied

from .defaults import get_comptes_setting


def scoping_enabled():
    return bool(get_comptes_setting("SCOPING_ENABLED", False))


def _validate_entreprise_id(value):
    if value is None:
        return ""
    value = str(value).strip()
    if scoping_enabled() and not value:
        raise PermissionDenied(
            "Aucune entreprise active n'a pu être déterminée pour cette requête."
        )
    return value


def resolve_entreprise_id(request):
    resolver = get_comptes_setting("SCOPE_RESOLVER")
    if resolver:
        if isinstance(resolver, str):
            module_path, function_name = resolver.rsplit(".", 1)
            resolver = getattr(import_module(module_path), function_name)
        return _validate_entreprise_id(resolver(request))

    for source in (request, getattr(request, "user", None)):
        if source is not None and hasattr(source, "entreprise_id"):
            return _validate_entreprise_id(getattr(source, "entreprise_id"))

    return _validate_entreprise_id("")


def scope_queryset(qs, entreprise_id):
    if not scoping_enabled():
        return qs
    return qs.filter(entreprise_id=_validate_entreprise_id(entreprise_id))


class EntrepriseScopedViewSetMixin:
    entreprise_scope_field = "entreprise_id"

    def get_entreprise_id(self):
        return resolve_entreprise_id(self.request)

    def get_queryset(self):
        qs = super().get_queryset()
        if scoping_enabled() and self.entreprise_scope_field:
            return qs.filter(
                **{self.entreprise_scope_field: self.get_entreprise_id()}
            )
        return qs

    def perform_create(self, serializer):
        if scoping_enabled() and "entreprise_id" in serializer.fields:
            serializer.save(entreprise_id=self.get_entreprise_id())
        else:
            serializer.save()
