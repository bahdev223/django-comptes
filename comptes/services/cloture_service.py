from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..models import Compte, JournalCompte, ClotureCompte, PeriodeCloture
from ..models import MouvementCompte, StatutMouvement, NatureMouvement
from ..signals.mouvement import compte_cloture
from .journal_service import JournalCompteService


class ClotureCompteService:
    """Cloture journaliere / periodique des comptes financiers."""

    @staticmethod
    @transaction.atomic
    def cloturer(compte, solde_reel=None, user=None, commentaire="", date_cloture=None):
        from datetime import date

        if date_cloture is None:
            date_cloture = date.today()

        if solde_reel is None:
            solde_reel = compte.solde_actuel

        journal = JournalCompteService.obtenir_ou_creer(compte, date_cloture)

        if journal.cloture:
            raise ValueError(f"Journal deja cloture pour {compte.nom} le {date_cloture}")

        entrees, sorties = JournalCompteService.calculer_totaux(compte, date_cloture)

        solde_ouverture = compte.solde_actuel - entrees + sorties
        solde_theorique = solde_ouverture + entrees - sorties
        ecart = solde_reel - solde_theorique

        journal.solde_ouverture = solde_ouverture
        journal.total_entrees = entrees
        journal.total_sorties = sorties
        journal.solde_theorique = solde_theorique
        journal.solde_reel = solde_reel
        journal.ecart = ecart
        journal.cloture = True
        journal.save()

        JournalCompteService.alimenter_lignes(journal)

        cloture = ClotureCompte.objects.create(
            compte=compte,
            periode=PeriodeCloture.QUOTIDIENNE,
            date_cloture=date_cloture,
            solde_avant=solde_theorique,
            solde_apres=solde_reel,
            ecart=ecart,
            commentaire=commentaire,
            cloture_par=user,
        )

        compte_cloture.send(
            sender=ClotureCompteService,
            instance=cloture,
            compte=compte,
            journal=journal,
            ecart=ecart,
            user=user,
        )

        return cloture
