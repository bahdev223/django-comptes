from decimal import Decimal

from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, When
from django.utils import timezone

from ..models import (
    Compte,
    HistoriqueCompte,
    MouvementCompte,
    NatureMouvement,
    SensMouvement,
    StatutMouvement,
    TypeChangement,
)
from ..permissions import require_comptes_permission


class CompteService:
    """Gestion des comptes financiers."""

    CHAMPS_MODIFIABLES = {
        "nom",
        "provider",
        "identifiant",
        "type",
        "role",
        "devise",
        "devise_id",
        "taux_change",
        "devise_reference",
        "actif",
        "autoriser_decouvert",
        "limite_decouvert",
        "date_fermeture",
        "compte_comptable_code",
        "accepte_ventes",
        "par_defaut",
    }

    TYPE_AUDIT = {
        "nom": TypeChangement.NOM,
        "type": TypeChangement.TYPE,
        "role": TypeChangement.ROLE,
        "devise": TypeChangement.DEVISE,
        "devise_id": TypeChangement.DEVISE,
        "actif": TypeChangement.ACTIVATION,
        "autoriser_decouvert": TypeChangement.DECOUVERT,
        "limite_decouvert": TypeChangement.LIMITE,
        "date_fermeture": TypeChangement.FERMETURE,
    }

    @staticmethod
    def creer(code, nom, type_compte, **kwargs):
        solde_initial = kwargs.pop("solde_initial", Decimal("0.00"))
        defaults = {
            "role": kwargs.pop("role", None),
            "devise_id": kwargs.pop("devise", "XOF"),
            "solde_initial": solde_initial,
            "solde_actuel": solde_initial,
            "actif": kwargs.pop("actif", True),
            "autoriser_decouvert": kwargs.pop("autoriser_decouvert", False),
            "limite_decouvert": kwargs.pop("limite_decouvert", Decimal("0.00")),
            "compte_comptable_code": kwargs.pop("compte_comptable_code", ""),
        }
        defaults.update(kwargs)
        return Compte.objects.create(
            code=code,
            nom=nom,
            type=type_compte,
            **defaults,
        )

    @staticmethod
    @transaction.atomic
    def modifier(compte, user=None, commentaire="", **kwargs):
        require_comptes_permission(user, "change_compte")

        changements = []
        for attr, value in kwargs.items():
            if attr not in CompteService.CHAMPS_MODIFIABLES or not hasattr(compte, attr):
                continue
            ancien = getattr(compte, attr)
            if ancien != value:
                changements.append((attr, ancien, value))
                setattr(compte, attr, value)

        if not changements:
            return compte

        compte.full_clean(exclude=["solde_initial", "solde_actuel"])
        compte.save()

        for attr, ancien, nouveau in changements:
            CompteService._historiser(
                compte=compte,
                type_changement=CompteService.TYPE_AUDIT.get(attr, TypeChangement.AUTRE),
                ancien=CompteService._audit_value(ancien),
                nouveau=CompteService._audit_value(nouveau),
                commentaire=commentaire or f"Modification du champ {attr}",
                user=user,
            )
        return compte

    @staticmethod
    def _audit_value(value):
        if value is None:
            return ""
        if hasattr(value, "pk"):
            return f"{value._meta.label_lower}:{value.pk}"
        return str(value)

    @staticmethod
    def desactiver(compte, user=None, raison=""):
        return CompteService.modifier(
            compte, user=user, commentaire=raison, actif=False
        )

    @staticmethod
    def activer(compte, user=None, raison=""):
        return CompteService.modifier(
            compte, user=user, commentaire=raison, actif=True
        )

    @staticmethod
    def fermer(compte, user=None, raison=""):
        return CompteService.modifier(
            compte,
            user=user,
            commentaire=raison,
            date_fermeture=timezone.now().date(),
            actif=False,
        )

    @staticmethod
    def recalculer_solde(compte):
        mouvements = MouvementCompte.objects.filter(
            compte=compte,
            statut__in=[StatutMouvement.VALIDE, StatutMouvement.RAPPROCHE],
        )
        signe = Case(
            When(sens=SensMouvement.ENTREE, then=F("montant")),
            When(sens=SensMouvement.SORTIE, then=-F("montant")),
            When(
                nature__in=[
                    NatureMouvement.ENCAISSEMENT,
                    NatureMouvement.TRANSFERT,
                    NatureMouvement.AJUSTEMENT,
                    NatureMouvement.OUVERTURE,
                ],
                then=F("montant"),
            ),
            default=-F("montant"),
            output_field=DecimalField(max_digits=15, decimal_places=2),
        )
        nouveau_solde = compte.solde_initial + (
            mouvements.aggregate(total=Sum(signe))["total"] or Decimal("0.00")
        )
        compte.solde_actuel = nouveau_solde
        compte.dernier_recalcul = timezone.now()
        compte.save(update_fields=["solde_actuel", "dernier_recalcul"])
        CompteService._historiser(
            compte,
            TypeChangement.RECALCUL,
            "",
            str(nouveau_solde),
            "Recalcul déterministe du solde",
            None,
        )
        return nouveau_solde

    @staticmethod
    def _historiser(compte, type_changement, ancien, nouveau, commentaire, user):
        HistoriqueCompte.objects.create(
            compte=compte,
            type_changement=type_changement,
            ancienne_valeur=ancien,
            nouvelle_valeur=nouveau,
            commentaire=commentaire,
            modifie_par=user,
        )
