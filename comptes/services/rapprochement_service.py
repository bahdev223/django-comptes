from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ..models import (
    Compte,
    RapprochementBancaire,
    LigneRapprochement,
    MouvementCompte,
    StatutMouvement,
    NatureMouvement,
    StatutRapprochement,
)
from ..selectors import MouvementSelector


class RapprochementService:
    """Rapprochement bancaire — pointage entre relevé et écritures."""

    @staticmethod
    @transaction.atomic
    def initialiser(compte, date_debut, date_fin, solde_releve, date_releve=None):
        if date_releve is None:
            date_releve = date_fin

        solde_comptable = (
            MouvementCompte.objects.filter(
                compte=compte,
                date__date__gte=date_debut,
                date__date__lte=date_fin,
                statut=StatutMouvement.VALIDE,
            ).aggregate(
                total=Sum("montant")
            )["total"]
            or Decimal("0.00")
        )

        rapprochement = RapprochementBancaire.objects.create(
            compte=compte,
            date_debut=date_debut,
            date_fin=date_fin,
            date_releve=date_releve,
            solde_releve=solde_releve,
            solde_comptable=solde_comptable,
            ecart=solde_comptable - solde_releve,
            statut=StatutRapprochement.EN_COURS,
        )

        mouvements = MouvementCompte.objects.filter(
            compte=compte,
            date__date__gte=date_debut,
            date__date__lte=date_fin,
            statut=StatutMouvement.VALIDE,
        )

        for mvt in mouvements:
            LigneRapprochement.objects.create(
                rapprochement=rapprochement,
                mouvement=mvt,
                type_ligne="COMPTABLE",
                montant=mvt.montant,
                date_operation=mvt.date.date(),
                libelle=mvt.libelle,
            )

        return rapprochement

    @staticmethod
    def pointer(rapprochement, ligne_id):
        """Marque une ligne comme pointée."""
        ligne = rapprochement.lignes.filter(id=ligne_id).first()
        if ligne:
            ligne.pointe = True
            ligne.save(update_fields=["pointe"])
            RapprochementService._mettre_a_jour_statut(rapprochement)
        return rapprochement

    @staticmethod
    def depointer(rapprochement, ligne_id):
        """Démarque une ligne pointée."""
        ligne = rapprochement.lignes.filter(id=ligne_id).first()
        if ligne:
            ligne.pointe = False
            ligne.save(update_fields=["pointe"])
            RapprochementService._mettre_a_jour_statut(rapprochement)
        return rapprochement

    @staticmethod
    def ajouter_ligne_releve(rapprochement, montant, date_operation, libelle, commentaire=""):
        """Ajoute une ligne issue du relevé bancaire (non présente en comptabilité)."""
        return LigneRapprochement.objects.create(
            rapprochement=rapprochement,
            type_ligne="RELEVE",
            montant=montant,
            date_operation=date_operation,
            libelle=libelle,
            commentaire=commentaire,
            pointe=False,
        )

    @staticmethod
    @transaction.atomic
    def valider(rapprochement, user=None):
        """Valide le rapprochement et bascule les mouvements en RAPPROCHE."""
        lignes_non_pointees = rapprochement.lignes.filter(
            type_ligne="COMPTABLE", pointe=False
        )

        if lignes_non_pointees.exists():
            raise ValueError(
                f"{lignes_non_pointees.count()} ligne(s) comptable(s) non pointée(s)"
            )

        lignes_ecart = rapprochement.lignes.filter(type_ligne="RELEVE")
        if lignes_ecart.exists():
            rapprochement.statut = StatutRapprochement.ECART
        else:
            rapprochement.statut = StatutRapprochement.EQUILIBRE

        rapprochement.date_validation = timezone.now()
        rapprochement.save()

        for ligne in rapprochement.lignes.filter(type_ligne="COMPTABLE", pointe=True):
            if ligne.mouvement:
                ligne.mouvement.statut = StatutMouvement.RAPPROCHE
                ligne.mouvement.save(update_fields=["statut"])

        return rapprochement

    @staticmethod
    def _mettre_a_jour_statut(rapprochement):
        total = rapprochement.lignes.count()
        pointees = rapprochement.lignes.filter(pointe=True).count()

        if total == 0:
            rapprochement.statut = StatutRapprochement.EN_COURS
        elif pointees == total:
            rapprochement.statut = StatutRapprochement.EQUILIBRE
        elif pointees > 0:
            rapprochement.statut = StatutRapprochement.PARTIEL
        else:
            rapprochement.statut = StatutRapprochement.EN_COURS

        rapprochement.save(update_fields=["statut"])
