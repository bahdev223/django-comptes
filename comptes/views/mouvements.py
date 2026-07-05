from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect
from django.contrib import messages

from ..models import Compte, MouvementCompte, StatutMouvement
from ..services import MouvementCompteService
from ..selectors import DashboardSelector, MouvementSelector


@login_required
def liste_mouvements(request):
    selector = MouvementSelector()
    mouvements = MouvementCompte.objects.select_related(
        "compte", "created_by"
    ).order_by("-date")[:200]
    comptes = Compte.objects.filter(actif=True).order_by("code")
    context = {
        "mouvements": mouvements,
        "comptes": comptes,
        "statuts": StatutMouvement.choices,
    }
    return render(request, "comptes/mouvements.html", context)


@login_required
@permission_required("comptes.encaisser", raise_exception=True)
def mouvement_encaisser(request):
    if request.method == "POST":
        try:
            compte = Compte.objects.get(id=request.POST.get("compte_id"), actif=True)
            montant = request.POST.get("montant")
            libelle = request.POST.get("libelle", "Encaissement")
            reference = request.POST.get("reference", "")
            MouvementCompteService.encaisser(
                compte=compte,
                montant=montant,
                libelle=libelle,
                user=request.user,
                reference=reference,
            )
            messages.success(request, f"Encaissement de {montant:,.0f} effectué")
        except Exception as e:
            messages.error(request, str(e))
    return redirect("comptes:dashboard")


@login_required
@permission_required("comptes.decaisser", raise_exception=True)
def mouvement_decaisser(request):
    if request.method == "POST":
        try:
            compte = Compte.objects.get(id=request.POST.get("compte_id"), actif=True)
            montant = request.POST.get("montant")
            libelle = request.POST.get("libelle", "Décaissement")
            reference = request.POST.get("reference", "")
            MouvementCompteService.decaisser(
                compte=compte,
                montant=montant,
                libelle=libelle,
                user=request.user,
                reference=reference,
            )
            messages.success(request, f"Décaissement de {montant:,.0f} effectué")
        except Exception as e:
            messages.error(request, str(e))
    return redirect("comptes:dashboard")
