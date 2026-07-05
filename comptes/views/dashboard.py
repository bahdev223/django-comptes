from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from ..models import Compte
from ..selectors import DashboardSelector


@login_required
def dashboard(request):
    selector = DashboardSelector()
    comptes = selector._filter_queryset(Compte.objects.filter(actif=True).order_by("code"))
    synthese = selector.synthese_globale()
    flux = selector.flux_24h()
    mouvements = selector.mouvements_recents(50)
    transferts = selector.transferts_recents(20)
    alertes = selector.alertes()

    context = {
        "comptes": comptes,
        "synthese": synthese,
        "flux_net": flux["flux_net"],
        "entrees_24h": flux["entrees"],
        "sorties_24h": flux["sorties"],
        "mouvements": mouvements,
        "transferts": transferts,
        "alertes": alertes,
    }
    return render(request, "comptes/dashboard.html", context)
