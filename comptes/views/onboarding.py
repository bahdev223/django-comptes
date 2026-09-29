from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render

from ..models import FinancialProvider, ProviderKind
from ..scoping import scoping_enabled
from ..services import FinancialOnboardingService
from .security import tenant_id


@login_required
@permission_required("comptes.add_compte", raise_exception=True)
def onboarding_financier(request):
    entreprise_id = tenant_id(request) if scoping_enabled() else ""

    if request.method == "POST":
        provider_codes = request.POST.getlist("providers")
        if not provider_codes:
            messages.error(request, "Sélectionnez au moins un moyen financier.")
        else:
            comptes = FinancialOnboardingService.configurer_comptes(
                provider_codes=provider_codes,
                entreprise_id=entreprise_id,
            )
            messages.success(
                request,
                f"{len(comptes)} compte(s) financier(s) configuré(s).",
            )
            return redirect("comptes:liste_comptes")

    providers = FinancialProvider.objects.filter(
        country_code="ML",
        active=True,
        selectable=True,
    ).order_by("kind", "sort_order", "name")

    groups = {
        "cash": [p for p in providers if p.kind == ProviderKind.CASH],
        "mobile_money": [p for p in providers if p.kind == ProviderKind.MOBILE_MONEY],
        "banks": [p for p in providers if p.kind == ProviderKind.BANK],
        "other": [
            p
            for p in providers
            if p.kind not in {ProviderKind.CASH, ProviderKind.MOBILE_MONEY, ProviderKind.BANK}
        ],
    }

    return render(
        request,
        "comptes/onboarding.html",
        {
            "groups": groups,
            "providers_available": providers.exists(),
        },
    )
