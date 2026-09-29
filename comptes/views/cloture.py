from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render

from ..models import JournalCompte
from ..services import ClotureCompteService
from .security import get_scoped_compte_or_404


@login_required
@permission_required("comptes.cloturer", raise_exception=True)
def cloturer_compte(request, compte_id):
    compte = get_scoped_compte_or_404(request, pk=compte_id, actif=True)

    if request.method == "POST":
        try:
            raw = request.POST.get("solde_reel")
            solde_reel = Decimal(raw) if raw not in (None, "") else None
            ClotureCompteService.cloturer(
                compte=compte,
                solde_reel=solde_reel,
                user=request.user,
                commentaire=request.POST.get("commentaire", ""),
            )
            messages.success(request, f"Clôture de {compte.nom} effectuée")
            return redirect("comptes:journal_consulter", compte_id=compte.id)
        except InvalidOperation:
            messages.error(request, "Solde réel invalide.")
        except Exception as exc:
            messages.error(request, str(exc))

    journal_ouvert = JournalCompte.objects.filter(
        compte=compte, cloture=False
    ).first()
    return render(
        request,
        "comptes/cloture.html",
        {"compte": compte, "journal": journal_ouvert},
    )
