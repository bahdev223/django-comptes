from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404

from ..models import Compte, RapprochementBancaire
from ..services import RapprochementService
from ..selectors import MouvementSelector


@login_required
def rapprochement_liste(request):
    rapprochements = RapprochementBancaire.objects.select_related("compte").order_by("-date_fin")
    comptes = Compte.objects.filter(type__in=["BANQUE", "MOBILE_MONEY"], actif=True)
    context = {
        "rapprochements": rapprochements,
        "comptes": comptes,
    }
    return render(request, "comptes/rapprochement.html", context)


@login_required
def rapprochement_detail(request, rapprochement_id):
    rapprochement = get_object_or_404(
        RapprochementBancaire.objects.select_related("compte"),
        id=rapprochement_id,
    )
    lignes = rapprochement.lignes.all().order_by("date_operation")
    context = {
        "rapprochement": rapprochement,
        "lignes": lignes,
    }
    return render(request, "comptes/rapprochement_detail.html", context)


@login_required
@permission_required("comptes.rapprocher", raise_exception=True)
def rapprochement_initialiser(request):
    if request.method == "POST":
        try:
            compte = Compte.objects.get(id=request.POST.get("compte_id"), actif=True)
            date_debut = request.POST.get("date_debut")
            date_fin = request.POST.get("date_fin")
            solde_releve = request.POST.get("solde_releve")
            date_releve = request.POST.get("date_releve", date_fin)

            rapprochement = RapprochementService.initialiser(
                compte=compte,
                date_debut=date_debut,
                date_fin=date_fin,
                solde_releve=solde_releve,
                date_releve=date_releve,
            )
            messages.success(request, "Rapprochement initialisé")
            return redirect("comptes:rapprochement_detail", rapprochement_id=rapprochement.id)
        except Exception as e:
            messages.error(request, str(e))
    return redirect("comptes:rapprochement_liste")
