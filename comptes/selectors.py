"""
Selectors — requetes complexes reutilisables.

Separation Query / Business Logic :
    Les services s'occupent de la logique metier (ecrire).
    Les selectors s'occupent des requetes de lecture (lire).
"""

from decimal import Decimal
from datetime import date, timedelta

from django.db.models import Sum, Q, Count
from django.utils import timezone

from .models import Compte, ModePaiement, MouvementCompte, TransfertCompte, JournalCompte
from .models import NatureMouvement, StatutMouvement, TypeCompte


class DashboardSelector:
    """Agregation des donnees pour le dashboard financier."""

    def __init__(self, tenant_filter=None):
        self.tenant_filter = tenant_filter or {}

    def _filter_queryset(self, qs):
        return qs.filter(**self.tenant_filter)

    def synthese_globale(self):
        """Solde total, repartition par type, nombre de comptes."""
        comptes = self._filter_queryset(Compte.objects.all())

        total = comptes.filter(actif=True).aggregate(
            nb=Count("id"),
        )
        soldes_par_devise = {
            row["devise_id"]: row["solde"] or Decimal("0.00")
            for row in comptes.filter(actif=True)
            .values("devise_id")
            .annotate(solde=Sum("solde_actuel"))
            .order_by("devise_id")
        }
        solde_total = (
            next(iter(soldes_par_devise.values()))
            if len(soldes_par_devise) == 1
            else None
        )

        par_type = {}
        for t in TypeCompte.values:
            qs = comptes.filter(type=t, actif=True).aggregate(
                solde=Sum("solde_actuel"),
                nb=Count("id"),
            )
            par_type[t] = qs

        alertes_decouvert = comptes.filter(
            actif=True, autoriser_decouvert=True, solde_actuel__lt=0
        ).count()

        return {
            "solde_total": solde_total,
            "soldes_par_devise": soldes_par_devise,
            "nb_comptes_actifs": total["nb"] or 0,
            "par_type": par_type,
            "alertes_decouvert": alertes_decouvert,
        }

    def flux_24h(self):
        """Entrees, sorties et flux net des dernieres 24h."""
        depuis = timezone.now() - timedelta(hours=24)
        mouvements = self._filter_queryset(
            MouvementCompte.objects.filter(date__gte=depuis, statut=StatutMouvement.VALIDE)
        )

        entrees = mouvements.filter(sens="ENTREE").aggregate(total=Sum("montant"))["total"] or Decimal("0.00")

        sorties = mouvements.filter(sens="SORTIE").aggregate(total=Sum("montant"))["total"] or Decimal("0.00")

        return {
            "entrees": entrees,
            "sorties": sorties,
            "flux_net": entrees - sorties,
        }

    def mouvements_recents(self, limite=20):
        """Derniers mouvements avec jointures optimisees."""
        return self._filter_queryset(
            MouvementCompte.objects.select_related("compte", "created_by")
        ).order_by("-date")[:limite]

    def alertes(self, seuil_caisse=Decimal("50000")):
        """Liste des alertes (comptes faibles, decouverts)."""
        comptes = self._filter_queryset(Compte.objects.filter(actif=True))
        alertes = []

        for c in comptes:
            if c.solde_actuel < seuil_caisse and not c.autoriser_decouvert:
                alertes.append({
                    "niveau": "warning",
                    "message": f"Solde faible: {c.nom} ({c.solde_actuel:,.0f} {c.devise})",
                    "compte": c,
                })
            if c.autoriser_decouvert and c.solde_actuel < 0:
                alertes.append({
                    "niveau": "danger",
                    "message": f"Découvert: {c.nom} ({c.solde_actuel:,.0f} {c.devise})",
                    "compte": c,
                })

        return alertes

    def transferts_recents(self, limite=20):
        return self._filter_queryset(
            TransfertCompte.objects.select_related("source", "destination", "valide_par")
        ).order_by("-date")[:limite]

    def journaux_ouverts(self):
        return self._filter_queryset(
            JournalCompte.objects.filter(cloture=False)
        ).select_related("compte")

    def compte_detail(self, compte_id):
        return self._filter_queryset(Compte.objects.filter(id=compte_id)).first()


class MouvementSelector:
    """Requetes sur les mouvements avec filtres."""

    def __init__(self, tenant_filter=None):
        self.tenant_filter = tenant_filter or {}

    def _filter_queryset(self, qs):
        return qs.filter(**self.tenant_filter)

    def historique_compte(self, compte_id, jours=90, limite=100):
        qs = self._filter_queryset(
            MouvementCompte.objects.filter(
                compte_id=compte_id,
                date__gte=timezone.now() - timedelta(days=jours),
            )
        ).select_related("created_by")
        return qs.order_by("-date")[:limite]

    def par_periode(self, debut, fin):
        return self._filter_queryset(
            MouvementCompte.objects.filter(date__date__gte=debut, date__date__lte=fin)
        ).select_related("compte", "created_by").order_by("-date")

    def non_rapproches(self, compte_id):
        return self._filter_queryset(
            MouvementCompte.objects.filter(
                compte_id=compte_id,
                statut__in=[StatutMouvement.VALIDE, StatutMouvement.BROUILLON],
            )
        ).order_by("date")


class ConfigurationFinanciereSelector:
    def __init__(self, entreprise_id=""):
        self.entreprise_id = entreprise_id

    def _accounts_queryset(self):
        return (
            Compte.objects.filter(entreprise_id=self.entreprise_id, actif=True)
            .select_related("provider")
            .order_by("code")
        )

    def configuration(self):
        accounts = list(self._accounts_queryset())
        active_payment_methods = self._active_payment_methods()
        has_cash = any(account.type == TypeCompte.ESPECES for account in accounts)
        has_mobile_money = any(account.type == TypeCompte.MOBILE_MONEY for account in accounts)
        has_bank = any(account.type == TypeCompte.BANQUE for account in accounts)

        return {
            "accounts": [self._account_payload(account) for account in accounts],
            "payment_methods": [mode.code for mode in active_payment_methods],
            "capabilities": {
                "has_cash": has_cash,
                "has_mobile_money": has_mobile_money,
                "has_bank": has_bank,
                "can_transfer": len(accounts) >= 2,
                "can_reconcile_bank": has_bank,
            },
        }

    def _active_payment_methods(self):
        return (
            ModePaiement.objects.filter(
                entreprise_id=self.entreprise_id,
                actif=True,
                liens_comptes__actif=True,
                liens_comptes__compte__actif=True,
                liens_comptes__compte__entreprise_id=self.entreprise_id,
            )
            .distinct()
            .order_by("libelle", "code")
        )

    def _account_payload(self, account):
        provider = account.provider
        return {
            "id": account.id,
            "name": account.nom,
            "type": account.type,
            "provider": provider.code if provider else None,
            "logo": provider.logo if provider else "",
        }
