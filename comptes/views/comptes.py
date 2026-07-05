from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404

from ..models import Compte
from ..services import CompteService
from ..selectors import DashboardSelector


@login_required
def liste_comptes(request):
    selector = DashboardSelector()
    comptes = Compte.objects.filter(actif=True).order_by("code")
    synthese = selector.synthese_globale()
    context = {
        "comptes": comptes,
        "synthese": synthese,
    }
    return render(request, "comptes/liste_comptes.html", context)


@login_required
def detail_compte(request, compte_id):
    compte = get_object_or_404(Compte, id=compte_id)
    historiques = compte.historique.all()[:20]
    context = {
        "compte": compte,
        "historiques": historiques,
    }
    return render(request, "comptes/detail_compte.html", context)


@login_required
@permission_required("comptes.add_compte", raise_exception=True)
def ajouter_compte(request):
    if request.method == "POST":
        try:
            code = request.POST.get("code")
            nom = request.POST.get("nom")
            type_compte = request.POST.get("type", "ESPECES")
            solde_initial = request.POST.get("solde_initial", 0)
            compte = CompteService.creer(
                code=code,
                nom=nom,
                type_compte=type_compte,
                solde_initial=solde_initial,
                actif=request.POST.get("actif") == "on",
                role=request.POST.get("role", ""),
                devise=request.POST.get("devise", "XOF"),
                compte_comptable_code=request.POST.get("compte_comptable_code", ""),
            )
            messages.success(request, f'Compte "{nom}" créé avec succès')
            return redirect("comptes:detail_compte", compte_id=compte.id)
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "comptes/form_compte.html", {"mode": "ajout"})


@login_required
@permission_required("comptes.change_compte", raise_exception=True)
def modifier_compte(request, compte_id):
    compte = get_object_or_404(Compte, id=compte_id)
    if request.method == "POST":
        try:
            CompteService.modifier(
                compte,
                nom=request.POST.get("nom"),
                type=request.POST.get("type"),
                role=request.POST.get("role", ""),
                actif=request.POST.get("actif") == "on",
                autoriser_decouvert=request.POST.get("autoriser_decouvert") == "on",
                limite_decouvert=request.POST.get("limite_decouvert", 0),
                compte_comptable_code=request.POST.get("compte_comptable_code", ""),
            )
            messages.success(request, f'Compte "{compte.nom}" modifié')
            return redirect("comptes:detail_compte", compte_id=compte.id)
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "comptes/form_compte.html", {"mode": "modification", "compte": compte})
