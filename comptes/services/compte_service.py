from decimal import Decimal

from django.db.models import Case, DecimalField, F, Sum, When
from django.utils import timezone

from ..models import Compte, MouvementCompte, HistoriqueCompte
from ..models import NatureMouvement, SensMouvement, StatutMouvement, TypeChangement


class CompteService:
    """Gestion des comptes financiers."""

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

        compte = Compte.objects.create(
            code=code,
            nom=nom,
            type=type_compte,
            **defaults,
        )
        return compte

    @staticmethod
    def modifier(compte, **kwargs):
        for attr, value in kwargs.items():
            if hasattr(compte, attr):
                setattr(compte, attr, value)
        compte.save()
        return compte

    @staticmethod
    def desactiver(compte, user=None, raison=""):
        ancien_actif = compte.actif
        compte.actif = False
        compte.save()
        CompteService._historiser(
            compte,
            TypeChangement.DESACTIVATION,
            str(ancien_actif),
            "False",
            raison,
            user,
        )

    @staticmethod
    def activer(compte, user=None, raison=""):
        ancien_actif = compte.actif
        compte.actif = True
        compte.save()
        CompteService._historiser(
            compte,
            TypeChangement.ACTIVATION,
            str(ancien_actif),
            "True",
            raison,
            user,
        )

    @staticmethod
    def fermer(compte, user=None, raison=""):
        compte.date_fermeture = timezone.now().date()
        compte.actif = False
        compte.save()
        CompteService._historiser(
            compte, TypeChangement.FERMETURE, "", raison, raison, user
        )

    @staticmethod
    def recalculer_solde(compte):
        """Recalcule le solde a partir de tous les mouvements valides."""
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
