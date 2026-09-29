from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render

from ..models import TransfertCompte
from ..services import TransfertCompteService
from .security import get_scoped_compte_or_404, scoped_comptes, scoped_queryset


@login_required
@permission_required("comptes.view_transfertcompte", raise_exception=True)
def liste_transferts(request):
    transferts = scoped_queryset(
        request,
        TransfertCompte.objects.select_related(
            "source", "destination", "valide_par"
        ),
    ).order_by("-date")[:100]
    return render(
        request,
        "comptes/transfert_liste.html",
        {"transferts": transferts},
    )


@login_required
@permission_required("comptes.transferer", raise_exception=True)
def transfert_effectuer(request):
    if request.method == "POST":
        try:
            source = get_scoped_compte_or_404(
                request, pk=request.POST.get("source_id"), actif=True
            )
            destination = get_scoped_compte_or_404(
                request, pk=request.POST.get("dest_id"), actif=True
            )
            try:
                montant = Decimal(request.POST.get("montant") or "")
            except InvalidOperation as exc:
                raise ValueError("Montant invalide.") from exc

            TransfertCompteService.transferer(
                source=source,
                destination=destination,
                montant=montant,
                user=request.user,
                notes=request.POST.get("notes", ""),
                idempotency_key=request.POST.get("idempotency_key") or None,
                source_system="django-html",
                source_type="manual-transfer",
            )
            messages.success(
                request, f"Transfert de {montant:,.0f} effectué avec succès"
            )
            return redirect("comptes:liste_transferts")
        except Exception as exc:
            messages.error(request, str(exc))

    comptes = scoped_comptes(request, actif=True).order_by("code")
    return render(request, "comptes/transfert.html", {"comptes": comptes})
