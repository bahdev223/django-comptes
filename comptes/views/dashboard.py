from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from ..models import Compte, Devise, FinancialProvider
from ..scoping import scoping_enabled
from ..selectors import DashboardSelector
from .security import scoped_comptes, tenant_id


@login_required
@permission_required("comptes.view_compte", raise_exception=True)
def dashboard(request):
    tenant_filter = (
        {"entreprise_id": tenant_id(request)}
        if scoping_enabled()
        else {}
    )
    selector = DashboardSelector(tenant_filter=tenant_filter)
    comptes = scoped_comptes(request, actif=True).select_related("provider", "devise").order_by("code")
    synthese = selector.synthese_globale()
    flux = selector.flux_24h()

    context = {
        "comptes": comptes,
        "synthese": synthese,
        "flux_net": flux["flux_net"],
        "entrees_24h": flux["entrees"],
        "sorties_24h": flux["sorties"],
        "mouvements": selector.mouvements_recents(8),
        "transferts": selector.transferts_recents(6),
        "alertes": selector.alertes(),
        "devises": Devise.objects.filter(actif=True).order_by("code"),
        "providers": FinancialProvider.objects.filter(
            country_code="ML", active=True, selectable=True
        ).order_by("kind", "sort_order", "name"),
    }
    return render(request, "comptes/dashboard.html", context)
