from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import (
    Compte,
    MouvementCompte,
    NatureMouvement,
    SensMouvement,
    StatutMouvement,
)
from ..signals.mouvement import mouvement_valide, mouvement_annule
from .compte_service import CompteService


class MouvementCompteService:
    """Service metier des mouvements de compte."""

    @staticmethod
    def encaisser(compte, montant, libelle, user, reference=None, source=None, idempotency_key=None):
        return MouvementCompteService._creer(
            compte=compte,
            nature=NatureMouvement.ENCAISSEMENT,
            montant=montant,
            libelle=libelle,
            user=user,
            reference=reference,
            source=source,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def decaisser(compte, montant, libelle, user, reference=None, source=None, idempotency_key=None):
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
        )

    @staticmethod
    def transfert(compte, montant, libelle, user, reference=None, source=None, sens=None):
        return MouvementCompteService._creer(
            compte=compte,
            nature=NatureMouvement.TRANSFERT,
            montant=montant,
            libelle=libelle,
            user=user,
            reference=reference,
            source=source,
            sens=sens,
        )

    @staticmethod
    def ajuster(compte, montant, libelle, user, reference=None, source=None):
        return MouvementCompteService._creer(
            compte=compte,
            nature=NatureMouvement.AJUSTEMENT,
            montant=montant,
            libelle=libelle,
            user=user,
            reference=reference,
            source=source,
        )

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
    ):
        montant = Decimal(str(montant))
        if montant <= 0:
            raise ValueError("Le montant doit etre positif")

        if idempotency_key:
            existing = MouvementCompte.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing

        compte = Compte.objects.select_for_update().get(pk=compte.pk)
        if not compte.actif:
            raise ValueError(f"Le compte {compte.nom} est inactif")
        if verifier_solde and compte.solde_disponible < montant:
            raise ValueError(
                f"Solde insuffisant. Disponible: {compte.solde_disponible:,.0f}, "
                f"Requis: {montant:,.0f}"
            )

        try:
            with transaction.atomic():
                mouvement = MouvementCompte.objects.create(
                    compte=compte,
                    nature=nature,
                    statut=StatutMouvement.VALIDE,
                    sens=sens or MouvementCompteService._sens_par_nature(nature),
                    montant=montant,
                    libelle=libelle,
                    reference=reference,
                    idempotency_key=idempotency_key,
                    created_by=user,
                )
        except IntegrityError:
            if idempotency_key:
                return MouvementCompte.objects.get(idempotency_key=idempotency_key)
            raise

        if source:
            from django.contrib.contenttypes.models import ContentType

            ct = ContentType.objects.get_for_model(source)
            mouvement.content_type = ct
            mouvement.object_id = source.pk
            mouvement.save(update_fields=["content_type", "object_id"])

        MouvementCompteService._mettre_a_jour_solde(compte, mouvement.sens, montant)

        mouvement_valide.send(
            sender=MouvementCompteService,
            instance=mouvement,
            nature=nature,
            montant=montant,
            user=user,
        )

        return mouvement

    @staticmethod
    @transaction.atomic
    def annuler(mouvement, user, raison=""):
        mouvement = MouvementCompte.objects.select_for_update().get(pk=mouvement.pk)
        if mouvement.statut == StatutMouvement.ANNULE:
            raise ValueError("Ce mouvement est deja annule")

        ancien_statut = mouvement.statut
        mouvement.statut = StatutMouvement.ANNULE
        mouvement.annule = True
        mouvement.annule_le = timezone.now()
        mouvement.annule_par = user
        mouvement.save(update_fields=["statut", "annule", "annule_le", "annule_par"])

        annulation = MouvementCompte.objects.create(
            compte=mouvement.compte,
            nature=NatureMouvement.ANNULATION,
            statut=StatutMouvement.VALIDE,
            sens=SensMouvement.SORTIE if mouvement.est_entree else SensMouvement.ENTREE,
            montant=mouvement.montant,
            libelle=f"ANNULATION - {mouvement.libelle} - {raison}".strip(),
            reference=mouvement.reference,
            created_by=user,
            mouvement_parent=mouvement,
        )

        MouvementCompteService._mettre_a_jour_solde(
            mouvement.compte, annulation.sens, mouvement.montant
        )

        mouvement_annule.send(
            sender=MouvementCompteService,
            instance=mouvement,
            annulation=annulation,
            user=user,
        )

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
