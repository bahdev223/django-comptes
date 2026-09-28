from decimal import Decimal
from uuid import uuid4

from django.db import IntegrityError, transaction

from ..defaults import get_comptes_setting
from ..exceptions import IdempotencyConflict
from ..integrity import payload_hash
from ..models import Compte, SensMouvement, TransfertCompte
from ..permissions import require_comptes_permission
from ..signals.mouvement import transfert_effectue
from .mouvement_service import MouvementCompteService


class TransfertCompteService:
    """Service de transfert atomique entre comptes financiers."""

    @staticmethod
    def _payload(
        source, destination, montant, notes,
        source_system, source_type, external_source_id, source_reference,
    ):
        return {
            "source_id": source.pk,
            "destination_id": destination.pk,
            "montant": format(montant, "f"),
            "notes": notes or "",
            "source_system": source_system or "",
            "source_type": source_type or "",
            "external_source_id": external_source_id or "",
            "source_reference": source_reference or "",
        }

    @staticmethod
    def _return_existing_or_conflict(existing, expected_hash):
        if existing.payload_hash and existing.payload_hash != expected_hash:
            raise IdempotencyConflict(
                "La clé d'idempotence du transfert existe avec un payload différent."
            )
        return existing

    @staticmethod
    @transaction.atomic
    def transferer(
        source, destination, montant, user, notes="", idempotency_key=None,
        source_system="", source_type="", external_source_id="", source_reference="",
    ):
        require_comptes_permission(user, "transferer")

        if source.id == destination.id:
            raise ValueError("Impossible de transférer vers le même compte")
        if source.entreprise_id != destination.entreprise_id:
            raise ValueError("Un transfert doit rester dans la même entreprise")

        montant = Decimal(str(montant))
        if montant <= 0:
            raise ValueError("Le montant doit être positif")

        hash_value = payload_hash(TransfertCompteService._payload(
            source, destination, montant, notes,
            source_system, source_type, external_source_id, source_reference,
        ))

        if idempotency_key:
            existing = TransfertCompte.objects.filter(
                entreprise_id=source.entreprise_id,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                return TransfertCompteService._return_existing_or_conflict(
                    existing, hash_value
                )

        comptes_verrouilles = Compte.objects.select_for_update().filter(
            id__in=[source.id, destination.id]
        ).order_by("id")
        comptes = {compte.pk: compte for compte in comptes_verrouilles}
        source = comptes[source.id]
        destination = comptes[destination.id]

        if source.entreprise_id != destination.entreprise_id:
            raise ValueError("Un transfert doit rester dans la même entreprise")
        if not source.actif:
            raise ValueError(f"Le compte source {source.nom} est inactif")
        if not destination.actif:
            raise ValueError(f"Le compte destination {destination.nom} est inactif")

        disponible = (
            source.solde_actuel + source.limite_decouvert
            if get_comptes_setting("ALLOW_OVERDRAFT", False) and source.autoriser_decouvert
            else source.solde_actuel
        )
        if disponible < montant:
            raise ValueError(
                f"Solde insuffisant dans {source.nom}. "
                f"Disponible: {disponible:,.0f}, Requis: {montant:,.0f}"
            )

        ref = f"TRF-{uuid4().hex[:16].upper()}"

        try:
            with transaction.atomic():
                transfert = TransfertCompte.objects.create(
                    source=source,
                    destination=destination,
                    montant=montant,
                    reference=ref,
                    entreprise_id=source.entreprise_id,
                    valide_par=user,
                    notes=notes,
                    idempotency_key=idempotency_key,
                    payload_hash=hash_value,
                    source_system=source_system or "",
                    source_type=source_type or "",
                    external_source_id=external_source_id or "",
                    source_reference=source_reference or "",
                )
        except IntegrityError:
            if idempotency_key:
                existing = TransfertCompte.objects.get(
                    entreprise_id=source.entreprise_id,
                    idempotency_key=idempotency_key,
                )
                return TransfertCompteService._return_existing_or_conflict(
                    existing, hash_value
                )
            raise

        trace_id = external_source_id or str(transfert.pk)
        MouvementCompteService.transfert(
            compte=source,
            montant=montant,
            libelle=f"Transfert vers {destination.nom}",
            user=user,
            reference=ref,
            sens=SensMouvement.SORTIE,
            source_system=source_system or "django-comptes",
            source_type=source_type or "transfert",
            source_id=trace_id,
            source_reference=source_reference or ref,
        )

        MouvementCompteService.transfert(
            compte=destination,
            montant=montant,
            libelle=f"Transfert depuis {source.nom}",
            user=user,
            reference=ref,
            sens=SensMouvement.ENTREE,
            source_system=source_system or "django-comptes",
            source_type=source_type or "transfert",
            source_id=trace_id,
            source_reference=source_reference or ref,
        )

        if get_comptes_setting("EMIT_DOMAIN_EVENTS", True):
            transaction.on_commit(lambda: transfert_effectue.send(
                sender=TransfertCompteService,
                instance=transfert,
                source=source,
                destination=destination,
                montant=montant,
                user=user,
            ))

        return transfert
