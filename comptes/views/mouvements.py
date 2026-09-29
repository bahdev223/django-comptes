from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render

from ..models import MouvementCompte, NatureMouvement, StatutMouvement
from ..services import MouvementCompteService
from .security import get_scoped_compte_or_404, scoped_comptes, scoped_queryset


@login_required
@permission_required("comptes.view_mouvementcompte", raise_exception=True)
def liste_mouvements(request):
    mouvements = scoped_queryset(
        request,
        MouvementCompte.objects.select_related("compte", "created_by"),
    ).order_by("-date")[:200]
    comptes = scoped_comptes(request, actif=True).order_by("code")
    return render(
        request,
        "comptes/mouvements.html",
        {
            "mouvements": mouvements,
            "comptes": comptes,
            "natures": NatureMouvement.choices,
            "statuts": StatutMouvement.choices,
        },
    )


def _montant_post(request):
    try:
        montant = Decimal(request.POST.get("montant") or "")
    except InvalidOperation as exc:
        raise ValueError("Montant invalide.") from exc
    if montant <= 0:
        raise ValueError("Le montant doit être positif.")
    return montant


@login_required
@permission_required("comptes.encaisser", raise_exception=True)
def mouvement_encaisser(request):
    if request.method != "POST":
        return redirect("comptes:liste_mouvements")
    try:
        compte = get_scoped_compte_or_404(
            request,
            pk=request.POST.get("compte_id"),
            actif=True,
        )
        montant = _montant_post(request)
        MouvementCompteService.encaisser(
            compte=compte,
            montant=montant,
            libelle=request.POST.get("libelle") or "Encaissement",
            user=request.user,
            reference=request.POST.get("reference", ""),
            idempotency_key=request.POST.get("idempotency_key") or None,
            source_system="django-html",
            source_type="manual",
        )
        messages.success(request, f"Encaissement de {montant:,.0f} effectué")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("comptes:liste_mouvements")


@login_required
@permission_required("comptes.decaisser", raise_exception=True)
def mouvement_decaisser(request):
    if request.method != "POST":
        return redirect("comptes:liste_mouvements")
    try:
        compte = get_scoped_compte_or_404(
            request,
            pk=request.POST.get("compte_id"),
            actif=True,
        )
        montant = _montant_post(request)
        MouvementCompteService.decaisser(
            compte=compte,
            montant=montant,
            libelle=request.POST.get("libelle") or "Décaissement",
            user=request.user,
            reference=request.POST.get("reference", ""),
            idempotency_key=request.POST.get("idempotency_key") or None,
            source_system="django-html",
            source_type="manual",
        )
        messages.success(request, f"Décaissement de {montant:,.0f} effectué")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("comptes:liste_mouvements")
