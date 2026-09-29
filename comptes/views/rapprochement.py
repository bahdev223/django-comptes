from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from ..models import RapprochementBancaire
from ..services import RapprochementService
from .security import get_scoped_compte_or_404, scoped_comptes, scoped_queryset


def _scoped_rapprochements(request):
    return scoped_queryset(
        request,
        RapprochementBancaire.objects.select_related("compte"),
        field="compte__entreprise_id",
    )


def _date_post(request, key, *, required=True):
    raw = request.POST.get(key)
    if not raw and not required:
        return None
    value = parse_date(raw or "")
    if value is None:
        raise ValueError(f"Date invalide : {key}.")
    return value


@login_required
@permission_required("comptes.view_rapprochementbancaire", raise_exception=True)
def rapprochement_liste(request):
    rapprochements = _scoped_rapprochements(request).order_by("-date_fin")
    comptes = scoped_comptes(request, actif=True).filter(
        type__in=["BANQUE", "MOBILE_MONEY"]
    )
    return render(
        request,
        "comptes/rapprochement.html",
        {"rapprochements": rapprochements, "comptes": comptes},
    )


@login_required
@permission_required("comptes.view_rapprochementbancaire", raise_exception=True)
def rapprochement_detail(request, rapprochement_id):
    rapprochement = get_object_or_404(
        _scoped_rapprochements(request),
        id=rapprochement_id,
    )
    lignes = rapprochement.lignes.all().order_by("date_operation", "id")
    return render(
        request,
        "comptes/rapprochement_detail.html",
        {"rapprochement": rapprochement, "lignes": lignes},
    )


@login_required
@permission_required("comptes.rapprocher", raise_exception=True)
def rapprochement_initialiser(request):
    if request.method != "POST":
        return redirect("comptes:rapprochement_liste")
    try:
        compte = get_scoped_compte_or_404(
            request, pk=request.POST.get("compte_id"), actif=True
        )
        date_debut = _date_post(request, "date_debut")
        date_fin = _date_post(request, "date_fin")
        date_releve = _date_post(request, "date_releve", required=False) or date_fin
        try:
            solde_releve = Decimal(request.POST.get("solde_releve") or "")
        except InvalidOperation as exc:
            raise ValueError("Solde relevé invalide.") from exc

        rapprochement = RapprochementService.initialiser(
            compte=compte,
            date_debut=date_debut,
            date_fin=date_fin,
            solde_releve=solde_releve,
            date_releve=date_releve,
            user=request.user,
        )
        messages.success(request, "Rapprochement initialisé")
        return redirect(
            "comptes:rapprochement_detail",
            rapprochement_id=rapprochement.id,
        )
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("comptes:rapprochement_liste")


@login_required
@permission_required("comptes.rapprocher", raise_exception=True)
def rapprochement_pointer(request, rapprochement_id, ligne_id):
    if request.method == "POST":
        rapprochement = get_object_or_404(
            _scoped_rapprochements(request), pk=rapprochement_id
        )
        try:
            RapprochementService.pointer(
                rapprochement, ligne_id, user=request.user
            )
            messages.success(request, "Ligne pointée.")
        except Exception as exc:
            messages.error(request, str(exc))
    return redirect(
        "comptes:rapprochement_detail",
        rapprochement_id=rapprochement_id,
    )


@login_required
@permission_required("comptes.rapprocher", raise_exception=True)
def rapprochement_depointer(request, rapprochement_id, ligne_id):
    if request.method == "POST":
        rapprochement = get_object_or_404(
            _scoped_rapprochements(request), pk=rapprochement_id
        )
        try:
            RapprochementService.depointer(
                rapprochement, ligne_id, user=request.user
            )
            messages.success(request, "Pointage retiré.")
        except Exception as exc:
            messages.error(request, str(exc))
    return redirect(
        "comptes:rapprochement_detail",
        rapprochement_id=rapprochement_id,
    )


@login_required
@permission_required("comptes.rapprocher", raise_exception=True)
def rapprochement_ajouter_ligne_releve(request, rapprochement_id):
    if request.method != "POST":
        return redirect(
            "comptes:rapprochement_detail",
            rapprochement_id=rapprochement_id,
        )
    rapprochement = get_object_or_404(
        _scoped_rapprochements(request), pk=rapprochement_id
    )
    try:
        try:
            montant = Decimal(request.POST.get("montant") or "")
        except InvalidOperation as exc:
            raise ValueError("Montant invalide.") from exc
        RapprochementService.ajouter_ligne_releve(
            rapprochement=rapprochement,
            montant=montant,
            date_operation=_date_post(request, "date_operation"),
            libelle=(request.POST.get("libelle") or "").strip(),
            commentaire=request.POST.get("commentaire", ""),
            user=request.user,
        )
        messages.success(request, "Ligne de relevé ajoutée.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect(
        "comptes:rapprochement_detail",
        rapprochement_id=rapprochement_id,
    )


@login_required
@permission_required("comptes.rapprocher", raise_exception=True)
def rapprochement_valider(request, rapprochement_id):
    if request.method == "POST":
        rapprochement = get_object_or_404(
            _scoped_rapprochements(request), pk=rapprochement_id
        )
        try:
            RapprochementService.valider(
                rapprochement, user=request.user
            )
            messages.success(request, "Rapprochement validé.")
        except Exception as exc:
            messages.error(request, str(exc))
    return redirect(
        "comptes:rapprochement_detail",
        rapprochement_id=rapprochement_id,
    )
