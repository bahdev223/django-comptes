from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404

from ..models import Compte, JournalCompte
from ..services import ClotureCompteService


@login_required
@permission_required("comptes.cloturer", raise_exception=True)
def cloturer_compte(request, compte_id):
    compte = get_object_or_404(Compte, id=compte_id, actif=True)

    if request.method == "POST":
        try:
            solde_reel = request.POST.get("solde_reel")
            commentaire = request.POST.get("commentaire", "")
            cloture = ClotureCompteService.cloturer(
                compte=compte,
                solde_reel=solde_reel,
                user=request.user,
                commentaire=commentaire,
            )
            messages.success(request, f"Clôture de {compte.nom} effectuée")
            return redirect("comptes:journal_consulter", compte_id=compte.id)
        except Exception as e:
            messages.error(request, str(e))

    journal_ouvert = JournalCompte.objects.filter(compte=compte, cloture=False).first()
    context = {
        "compte": compte,
        "journal": journal_ouvert,
    }
    return render(request, "comptes/cloture.html", context)
