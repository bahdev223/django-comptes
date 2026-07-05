from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect

from ..models import Compte, TransfertCompte
from ..services import TransfertCompteService


@login_required
def liste_transferts(request):
    transferts = TransfertCompte.objects.select_related(
        "source", "destination", "valide_par"
    ).order_by("-date")[:100]
    return render(request, "comptes/transfert_liste.html", {"transferts": transferts})


@login_required
@permission_required("comptes.transferer", raise_exception=True)
def transfert_effectuer(request):
    if request.method == "POST":
        try:
            source = Compte.objects.get(id=request.POST.get("source_id"), actif=True)
            destination = Compte.objects.get(id=request.POST.get("dest_id"), actif=True)
            montant = request.POST.get("montant")
            notes = request.POST.get("notes", "")

            transfert = TransfertCompteService.transferer(
                source=source,
                destination=destination,
                montant=montant,
                user=request.user,
                notes=notes,
            )
            messages.success(request, f"Transfert de {montant:,.0f} effectué avec succès")
            return redirect("comptes:liste_transferts")
        except Exception as e:
            messages.error(request, str(e))

    comptes = Compte.objects.filter(actif=True).order_by("code")
    return render(request, "comptes/transfert.html", {"comptes": comptes})
