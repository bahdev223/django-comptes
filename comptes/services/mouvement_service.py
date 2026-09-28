from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..defaults import get_comptes_setting
from ..exceptions import IdempotencyConflict
from ..integrity import payload_hash
from ..models import (
    Compte,
    MouvementCompte,
    NatureMouvement,
    SensMouvement,
    StatutMouvement,
)
from ..permissions import require_comptes_permission
from ..signals.mouvement import mouvement_annule, mouvement_valide


class MouvementCompteService:
    """Service métier des mouvements de compte."""

    @staticmethod
    def encaisser(
        compte, montant, libelle, user, reference=None, source=None,
        idempotency_key=None, source_system="", source_type="", source_id="",
        source_reference="",
    ):
        require_comptes_permission(user, "encaisser")
        return MouvementCompteService._creer(
            compte=compte,
            nature=NatureMouvement.ENCAISSEMENT,
            montant=montant,
            libelle=libelle,
            user=user,
            reference=reference,
            source=source,
            idempotency_key=idempotency_key,
            source_system=source_system,
            source_type=source_type,
            source_id=source_id,
            source_reference=source_reference,
        )

    @staticmethod
    def decaisser(
        compte, montant, libelle, user, reference=None, source=None,
        idempotency_key=None, source_system="", source_type="", source_id="",
        source_reference="",
    ):
        require_comptes_permission(user, "decaisser")
        return MouvementCompteService._creer(
            compte=compte,
            nature=NatureMouvement.DECAISSEMENT,
            montant=montant,
            libelle=libelle,
            user=user,
            reference=reference,
            source=source,
            idempotency_key=idempotency_key,
            verifier_solde=True,
            source_system=source_system,
            source_type=source_type,
            source_id=source_id,
            source_reference=source_reference,
        )

    @staticmethod
    def transfert(
        compte, montant, libelle, user, reference=None, source=None, sens=None,
        source_system="", source_type="", source_id="", source_reference="",
    ):
        return MouvementCompteService._creer(
            compte=compte,
            nature=NatureMouvement.TRANSFERT,
            montant=montant,
            libelle=libelle,
            user=user,
            reference=reference,
            source=source,
            sens=sens,
            source_system=source_system,
            source_type=source_type,
            source_id=source_id,
            source_reference=source_reference,
        )

    @staticmethod
    def ajuster(
        compte, montant, libelle, user, reference=None, source=None,
        idempotency_key=None, sens=None, source_system="", source_type="",
        source_id="", source_reference="",
    ):
        require_comptes_permission(user, "change_compte")
        return MouvementCompteService._creer(
            compte=compte,
            nature=NatureMouvement.AJUSTEMENT,
            montant=montant,
            libelle=libelle,
            user=user,
            reference=reference,
            source=source,
            idempotency_key=idempotency_key,
            sens=sens,
            source_system=source_system,
            source_type=source_type,
            source_id=source_id,
            source_reference=source_reference,
        )

    @staticmethod
    def _payload(
        compte, nature, sens, montant, libelle, reference,
        source_system, source_type, source_id, source_reference, source,
    ):
        generic_source = None
        if source is not None:
            generic_source = {
                "model": source._meta.label_lower,
                "pk": str(source.pk),
            }
        return {
            "compte_id": compte.pk,
            "nature": str(nature),
            "sens": str(sens),
            "montant": format(montant, "f"),
            "libelle": libelle or "",
            "reference": reference or "",
            "source_system": source_system or "",
            "source_type": source_type or "",
            "source_id": source_id or "",
            "source_reference": source_reference or "",
            "generic_source": generic_source,
        }

    @staticmethod
    def _return_existing_or_conflict(existing, expected_hash):
        if existing.payload_hash and existing.payload_hash != expected_hash:
            raise IdempotencyConflict(
                "La clé d'idempotence existe déjà avec un payload différent."
            )
        return existing

    @staticmethod
    @transaction.atomic
    def _creer(
        compte,
        nature,
        montant,
        libelle,
        user,
        reference=None,
        source=None,
        idempotency_key=None,
        verifier_solde=False,
        sens=None,
        source_system="",
        source_type="",
        source_id="",
        source_reference="",
    ):
        montant = Decimal(str(montant))
        if montant <= 0:
            raise ValueError("Le montant doit être positif")

        sens_effectif = sens or MouvementCompteService._sens_par_nature(nature)
        hash_value = payload_hash(MouvementCompteService._payload(
            compte, nature, sens_effectif, montant, libelle, reference,
            source_system, source_type, source_id, source_reference, source,
        ))

        if idempotency_key:
            existing = MouvementCompte.objects.filter(
                entreprise_id=compte.entreprise_id,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                return MouvementCompteService._return_existing_or_conflict(
                    existing, hash_value
                )

        compte = Compte.objects.select_for_update().get(pk=compte.pk)
        if not compte.actif:
            raise ValueError(f"Le compte {compte.nom} est inactif")

        if get_comptes_setting("LOCK_CLOSED_PERIODS", True):
            from datetime import date
            from ..models import ClotureCompte, PeriodeCloture

            if ClotureCompte.objects.filter(
                compte=compte,
                periode=PeriodeCloture.QUOTIDIENNE,
                date_cloture=date.today(),
            ).exists():
                raise ValueError("Ce compte est clôturé pour aujourd'hui.")

        autoriser_decouvert = (
            get_comptes_setting("ALLOW_OVERDRAFT", False) and compte.autoriser_decouvert
        )
        disponible = (
            compte.solde_actuel + compte.limite_decouvert
            if autoriser_decouvert else compte.solde_actuel
        )
        if verifier_solde and disponible < montant:
            raise ValueError(
                f"Solde insuffisant. Disponible: {disponible:,.0f}, "
                f"Requis: {montant:,.0f}"
            )

        lien = {}
        if source:
            from django.contrib.contenttypes.models import ContentType
            lien = {
                "content_type": ContentType.objects.get_for_model(source),
                "object_id": source.pk,
            }

        try:
            with transaction.atomic():
                mouvement = MouvementCompte.objects.create(
                    compte=compte,
                    nature=nature,
                    statut=StatutMouvement.VALIDE,
                    sens=sens_effectif,
                    montant=montant,
                    libelle=libelle,
                    reference=reference,
                    entreprise_id=compte.entreprise_id,
                    idempotency_key=idempotency_key,
                    payload_hash=hash_value,
                    source_system=source_system or "",
                    source_type=source_type or "",
                    source_id=source_id or "",
                    source_reference=source_reference or "",
                    created_by=user,
                    **lien,
                )
        except IntegrityError:
            if idempotency_key:
                existing = MouvementCompte.objects.get(
                    entreprise_id=compte.entreprise_id,
                    idempotency_key=idempotency_key,
                )
                return MouvementCompteService._return_existing_or_conflict(
                    existing, hash_value
                )
            raise

        MouvementCompteService._mettre_a_jour_solde(compte, mouvement.sens, montant)

        if get_comptes_setting("EMIT_DOMAIN_EVENTS", True):
            transaction.on_commit(lambda: mouvement_valide.send(
                sender=MouvementCompteService,
                instance=mouvement,
                nature=nature,
                montant=montant,
                user=user,
            ))

        return mouvement

    @staticmethod
    @transaction.atomic
    def annuler(mouvement, user, raison=""):
        require_comptes_permission(user, "annuler")
        mouvement = MouvementCompte.objects.select_for_update().get(pk=mouvement.pk)
        if mouvement.statut == StatutMouvement.ANNULE:
            raise ValueError("Ce mouvement est déjà annulé")

        mouvement.statut = StatutMouvement.ANNULE
        mouvement.annule = True
        mouvement.annule_le = timezone.now()
        mouvement.annule_par = user
        mouvement.save(update_fields=["statut", "annule", "annule_le", "annule_par"])

        sens_annulation = (
            SensMouvement.SORTIE if mouvement.est_entree else SensMouvement.ENTREE
        )
        annulation_payload = {
            "mouvement_parent": mouvement.pk,
            "sens": sens_annulation,
            "montant": format(mouvement.montant, "f"),
            "raison": raison or "",
        }
        annulation = MouvementCompte.objects.create(
            compte=mouvement.compte,
            nature=NatureMouvement.ANNULATION,
            statut=StatutMouvement.VALIDE,
            sens=sens_annulation,
            montant=mouvement.montant,
            libelle=f"ANNULATION - {mouvement.libelle} - {raison}".strip(),
            reference=mouvement.reference,
            entreprise_id=mouvement.entreprise_id,
            payload_hash=payload_hash(annulation_payload),
            source_system=mouvement.source_system,
            source_type=mouvement.source_type,
            source_id=mouvement.source_id,
            source_reference=mouvement.source_reference,
            created_by=user,
            mouvement_parent=mouvement,
        )

        MouvementCompteService._mettre_a_jour_solde(
            mouvement.compte, annulation.sens, mouvement.montant
        )

        if get_comptes_setting("EMIT_DOMAIN_EVENTS", True):
            transaction.on_commit(lambda: mouvement_annule.send(
                sender=MouvementCompteService,
                instance=mouvement,
                annulation=annulation,
                user=user,
            ))

        return annulation

    @staticmethod
    def _sens_par_nature(nature):
        if nature in (
            NatureMouvement.ENCAISSEMENT,
            NatureMouvement.TRANSFERT,
            NatureMouvement.AJUSTEMENT,
            NatureMouvement.OUVERTURE,
        ):
            return SensMouvement.ENTREE
        return SensMouvement.SORTIE

    @staticmethod
    def _mettre_a_jour_solde(compte, sens, montant):
        sign = +1 if sens == SensMouvement.ENTREE else -1
        compte.solde_actuel += sign * montant
        compte.save(update_fields=["solde_actuel"])
