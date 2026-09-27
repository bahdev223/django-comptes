from decimal import Decimal

from django.db import transaction

from ..models import Compte, FinancialProvider, ModePaiement, ProviderKind, RoleCompte, TypeCompte


PROVIDER_KIND_TO_TYPE_COMPTE = {
    ProviderKind.CASH: TypeCompte.ESPECES,
    ProviderKind.MOBILE_MONEY: TypeCompte.MOBILE_MONEY,
    ProviderKind.BANK: TypeCompte.BANQUE,
    ProviderKind.PAYMENT_INSTITUTION: TypeCompte.AUTRE,
    ProviderKind.OTHER: TypeCompte.AUTRE,
}


class FinancialProviderService:
    @staticmethod
    def synchroniser(providers):
        synced = []
        for data in providers:
            payload = dict(data)
            code = payload.pop("code").strip().upper()
            provider, _ = FinancialProvider.objects.update_or_create(
                code=code,
                defaults=payload,
            )
            synced.append(provider)
        return synced


class FinancialOnboardingService:
    @staticmethod
    @transaction.atomic
    def configurer_comptes(
        provider_codes,
        entreprise_id="",
        comptes_personnalises=None,
        devise="XOF",
    ):
        comptes = []
        for provider in FinancialOnboardingService._providers_choisis(provider_codes):
            compte = FinancialOnboardingService._creer_ou_obtenir_compte_provider(
                provider=provider,
                entreprise_id=entreprise_id,
                devise=devise,
            )
            comptes.append(compte)
            FinancialOnboardingService._creer_mode_paiement(compte)

        for data in comptes_personnalises or []:
            compte = FinancialOnboardingService._creer_compte_personnalise(
                data=data,
                entreprise_id=entreprise_id,
                devise=devise,
            )
            comptes.append(compte)
            FinancialOnboardingService._creer_mode_paiement(compte)

        return comptes

    @staticmethod
    def _providers_choisis(provider_codes):
        normalized_codes = [code.strip().upper() for code in provider_codes]
        providers = list(
            FinancialProvider.objects.filter(
                code__in=normalized_codes,
                active=True,
                selectable=True,
            )
        )
        providers_by_code = {provider.code: provider for provider in providers}
        return [providers_by_code[code] for code in normalized_codes if code in providers_by_code]

    @staticmethod
    def _creer_ou_obtenir_compte_provider(provider, entreprise_id, devise):
        code = FinancialOnboardingService._code_compte(provider)
        defaults = {
            "nom": FinancialOnboardingService._nom_compte(provider),
            "type": PROVIDER_KIND_TO_TYPE_COMPTE[provider.kind],
            "role": RoleCompte.CAISSE if provider.kind == ProviderKind.CASH else None,
            "devise_id": devise,
            "solde_initial": Decimal("0.00"),
            "solde_actuel": Decimal("0.00"),
            "actif": True,
            "accepte_ventes": provider.kind in {ProviderKind.CASH, ProviderKind.MOBILE_MONEY},
        }
        compte, _ = Compte.objects.get_or_create(
            entreprise_id=entreprise_id,
            code=code,
            defaults={**defaults, "provider": provider},
        )
        return compte

    @staticmethod
    def _creer_compte_personnalise(data, entreprise_id, devise):
        nom = data["nom"].strip()
        type_compte = data.get("type_compte", TypeCompte.AUTRE)
        base_code = data.get("code") or nom.upper().replace(" ", "_").replace("-", "_")
        code = base_code[:20]
        compte, _ = Compte.objects.get_or_create(
            entreprise_id=entreprise_id,
            code=code,
            defaults={
                "nom": nom,
                "type": type_compte,
                "devise_id": devise,
                "identifiant": data.get("identifiant", ""),
                "solde_initial": data.get("solde_initial", Decimal("0.00")),
                "solde_actuel": data.get("solde_initial", Decimal("0.00")),
                "actif": True,
                "accepte_ventes": data.get("accepte_ventes", True),
            },
        )
        return compte

    @staticmethod
    def _creer_mode_paiement(compte):
        if not compte.accepte_ventes:
            return None
        code = compte.provider.code if compte.provider else compte.code
        mode, _ = ModePaiement.objects.get_or_create(
            code=code,
            defaults={"libelle": compte.provider.name if compte.provider else compte.nom},
        )
        mode.comptes.add(compte)
        return mode

    @staticmethod
    def _code_compte(provider):
        if provider.kind == ProviderKind.CASH:
            return "CAISSE"
        return provider.code[:20]

    @staticmethod
    def _nom_compte(provider):
        if provider.kind == ProviderKind.CASH:
            return "Caisse"
        return provider.name
