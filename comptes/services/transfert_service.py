from decimal import Decimal
from uuid import uuid4

from django.db import transaction

from ..models import Compte, TransfertCompte
from ..models import SensMouvement
from ..signals.mouvement import transfert_effectue
from .mouvement_service import MouvementCompteService


class TransfertCompteService:
    """Service de transfert atomique entre comptes financiers."""

    @staticmethod
    @transaction.atomic
    def transferer(source, destination, montant, user, notes="", idempotency_key=None):
        if idempotency_key:
            existing = TransfertCompte.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing

        if source.id == destination.id:
            raise ValueError("Impossible de transferer vers le meme compte")
        if not source.actif:
            raise ValueError(f"Le compte source {source.nom} est inactif")
        if not destination.actif:
            raise ValueError(f"Le compte destination {destination.nom} est inactif")

        montant = Decimal(str(montant))
        if montant <= 0:
            raise ValueError("Le montant doit etre positif")

        comptes_verrouilles = Compte.objects.select_for_update().filter(
            id__in=[source.id, destination.id]
        ).order_by("id")
        comptes = {compte.pk: compte for compte in comptes_verrouilles}
        source = comptes[source.id]
        destination = comptes[destination.id]

        if source.solde_disponible < montant:
            raise ValueError(
                f"Solde insuffisant dans {source.nom}. "
                f"Disponible: {source.solde_disponible:,.0f}, Requis: {montant:,.0f}"
            )

        ref = f"TRF-{uuid4().hex[:16].upper()}"

        sortie = MouvementCompteService.transfert(
            compte=source,
            montant=montant,
            libelle=f"Transfert vers {destination.nom}",
            user=user,
            reference=ref,
            sens=SensMouvement.SORTIE,
        )

        entree = MouvementCompteService.transfert(
            compte=destination,
            montant=montant,
            libelle=f"Transfert depuis {source.nom}",
            user=user,
            reference=ref,
            sens=SensMouvement.ENTREE,
        )

        transfert = TransfertCompte.objects.create(
            source=source,
            destination=destination,
            montant=montant,
            reference=ref,
            valide_par=user,
            notes=notes,
            idempotency_key=idempotency_key,
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
