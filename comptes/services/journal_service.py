from decimal import Decimal

from django.db.models import Sum

from ..models import JournalCompte, LigneJournalCompte, MouvementCompte
from ..models import NatureMouvement, StatutMouvement


class JournalCompteService:
    """Consultation et generation des journaux de compte."""

    @staticmethod
    def obtenir_ou_creer(compte, date_journal=None):
        """Retourne le journal du jour, le cree si necessaire."""
        from datetime import date

        if date_journal is None:
            date_journal = date.today()

        journal, created = JournalCompte.objects.get_or_create(
            compte=compte,
            date_journal=date_journal,
            defaults={
                "solde_ouverture": compte.solde_actuel,
            },
        )
        return journal

    @staticmethod
    def calculer_totaux(compte, date_journal):
        """Calcule totaux entree/sortie pour un compte a une date donnee."""
        mouvements = MouvementCompte.objects.filter(
            compte=compte,
            date__date=date_journal,
            statut=StatutMouvement.VALIDE,
        )

        entrees = (
            mouvements.filter(
                nature__in=[
                    NatureMouvement.ENCAISSEMENT,
                    NatureMouvement.TRANSFERT,
                    NatureMouvement.AJUSTEMENT,
                    NatureMouvement.OUVERTURE,
                ]
            ).aggregate(total=Sum("montant"))["total"]
            or Decimal("0.00")
        )

        sorties = (
            mouvements.filter(
                nature__in=[NatureMouvement.DECAISSEMENT, NatureMouvement.ANNULATION]
            ).aggregate(total=Sum("montant"))["total"]
            or Decimal("0.00")
        )

        return entrees, sorties

    @staticmethod
    def alimenter_lignes(journal):
        """Remplit les lignes du journal a partir des mouvements valides."""
        mouvements = MouvementCompte.objects.filter(
            compte=journal.compte,
            date__date=journal.date_journal,
            statut=StatutMouvement.VALIDE,
        )

        lignes = []
        for mvt in mouvements:
            sens = "ENTREE" if mvt.nature in (
                NatureMouvement.ENCAISSEMENT,
                NatureMouvement.TRANSFERT,
                NatureMouvement.AJUSTEMENT,
                NatureMouvement.OUVERTURE,
            ) else "SORTIE"

            ligne, created = LigneJournalCompte.objects.get_or_create(
                journal=journal,
                reference=mvt.reference or "",
                defaults={
                    "type_operation": mvt.libelle,
                    "nature": mvt.nature,
                    "montant": mvt.montant,
                    "sens": sens,
                    "reference": mvt.reference or "",
                    "libelle": mvt.libelle,
                },
            )
            lignes.append(ligne)

        return lignes
