from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Devise
from ..selectors import DashboardSelector
from ..services import CompteService
from .security import get_scoped_compte_or_404, scoped_comptes, tenant_id
from ..scoping import scoping_enabled


def _tenant_filter(request):
    return {"entreprise_id": tenant_id(request)} if scoping_enabled() else {}


@login_required
@permission_required("comptes.view_compte", raise_exception=True)
def liste_comptes(request):
    comptes = scoped_comptes(request, actif=True).order_by("code")
    synthese = DashboardSelector(tenant_filter=_tenant_filter(request)).synthese_globale()
    return render(
        request,
        "comptes/liste_comptes.html",
        {
            "comptes": comptes,
            "synthese": synthese,
            "devises": Devise.objects.filter(actif=True).order_by("code"),
        },
    )


@login_required
@permission_required("comptes.view_compte", raise_exception=True)
def detail_compte(request, compte_id):
    compte = get_scoped_compte_or_404(request, pk=compte_id)
    historiques = compte.historique.all()[:20]
    return render(
        request,
        "comptes/detail_compte.html",
        {"compte": compte, "historiques": historiques},
    )


@login_required
@permission_required("comptes.add_compte", raise_exception=True)
def ajouter_compte(request):
    if request.method == "POST":
        try:
            solde_initial = Decimal(request.POST.get("solde_initial") or "0")
            kwargs = {
                "code": (request.POST.get("code") or "").strip(),
                "nom": (request.POST.get("nom") or "").strip(),
                "type_compte": request.POST.get("type", "ESPECES"),
                "solde_initial": solde_initial,
                "actif": request.POST.get("actif") == "on",
                "role": request.POST.get("role") or None,
                "devise": request.POST.get("devise", "XOF"),
                "compte_comptable_code": request.POST.get("compte_comptable_code", ""),
            }
            if scoping_enabled():
                kwargs["entreprise_id"] = tenant_id(request)
            compte = CompteService.creer(**kwargs)
            messages.success(request, f'Compte "{compte.nom}" créé avec succès')
            return redirect("comptes:detail_compte", compte_id=compte.id)
        except (InvalidOperation, ValueError) as exc:
            messages.error(request, f"Données invalides : {exc}")
        except Exception as exc:
            messages.error(request, str(exc))

    return render(
        request,
        "comptes/form_compte.html",
        {"mode": "ajout", "devises": Devise.objects.filter(actif=True)},
    )


@login_required
@permission_required("comptes.change_compte", raise_exception=True)
def modifier_compte(request, compte_id):
    compte = get_scoped_compte_or_404(request, pk=compte_id)
    if request.method == "POST":
        try:
            CompteService.modifier(
                compte,
                user=request.user,
                commentaire="Modification via interface Django",
                nom=(request.POST.get("nom") or "").strip(),
                type=request.POST.get("type"),
                role=request.POST.get("role") or None,
                actif=request.POST.get("actif") == "on",
                autoriser_decouvert=request.POST.get("autoriser_decouvert") == "on",
                limite_decouvert=Decimal(request.POST.get("limite_decouvert") or "0"),
                compte_comptable_code=request.POST.get("compte_comptable_code", ""),
            )
            messages.success(request, f'Compte "{compte.nom}" modifié')
            return redirect("comptes:detail_compte", compte_id=compte.id)
        except (InvalidOperation, ValueError) as exc:
            messages.error(request, f"Données invalides : {exc}")
        except Exception as exc:
            messages.error(request, str(exc))

    return render(
        request,
        "comptes/form_compte.html",
        {
            "mode": "modification",
            "compte": compte,
            "devises": Devise.objects.filter(actif=True),
        },
    )
