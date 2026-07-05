from django.db import transaction

from ..models import Compte, TransfertCompte
from ..signals.mouvement import transfert_effectue
from .mouvement_service import MouvementCompteService


class TransfertCompteService:
    """Service de transfert atomique entre comptes financiers."""

    @staticmethod
    @transaction.atomic
    def transferer(source, destination, montant, user, notes=""):
        if source.id == destination.id:
            raise ValueError("Impossible de transferer vers le meme compte")
        if not source.actif:
            raise ValueError(f"Le compte source {source.nom} est inactif")
        if not destination.actif:
            raise ValueError(f"Le compte destination {destination.nom} est inactif")

        from decimal import Decimal

        montant = Decimal(str(montant))
        if montant <= 0:
            raise ValueError("Le montant doit etre positif")

        if source.solde_disponible < montant:
            raise ValueError(
                f"Solde insuffisant dans {source.nom}. "
                f"Disponible: {source.solde_disponible:,.0f}, Requis: {montant:,.0f}"
            )

        ref = f"TRF-{source.code}-{destination.code}-{source.mouvements.count() + 1}"

        sortie = MouvementCompteService.transfert(
            compte=source,
            montant=montant,
            libelle=f"Transfert vers {destination.nom}",
            user=user,
            reference=ref,
        )

        entree = MouvementCompteService.transfert(
            compte=destination,
            montant=montant,
            libelle=f"Transfert depuis {source.nom}",
            user=user,
            reference=ref,
        )

        transfert = TransfertCompte.objects.create(
            source=source,
            destination=destination,
            montant=montant,
            reference=ref,
            valide_par=user,
            notes=notes,
        )

        transfert_effectue.send(
            sender=TransfertCompteService,
            instance=transfert,
            source=source,
            destination=destination,
            montant=montant,
            user=user,
        )

        return transfert
