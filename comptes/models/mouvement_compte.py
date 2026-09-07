from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .compte import Compte


class NatureMouvement(models.TextChoices):
    ENCAISSEMENT = "ENCAISSEMENT", _("Encaissement")
    DECAISSEMENT = "DECAISSEMENT", _("Décaissement")
    TRANSFERT = "TRANSFERT", _("Transfert")
    AJUSTEMENT = "AJUSTEMENT", _("Ajustement")
    OUVERTURE = "OUVERTURE", _("Solde initial / Ouverture")
    CLOTURE = "CLOTURE", _("Clôture")
    ANNULATION = "ANNULATION", _("Annulation")


class StatutMouvement(models.TextChoices):
    BROUILLON = "BROUILLON", _("Brouillon")
    VALIDE = "VALIDE", _("Validé")
    ANNULE = "ANNULE", _("Annulé")
    RAPPROCHE = "RAPPROCHE", _("Rapproché")


class SensMouvement(models.TextChoices):
    ENTREE = "ENTREE", _("Entrée")
    SORTIE = "SORTIE", _("Sortie")


class MouvementCompte(models.Model):
    compte = models.ForeignKey(
        Compte, on_delete=models.PROTECT, related_name="mouvements", verbose_name=_("Compte")
    )
    nature = models.CharField(
        _("Nature"), max_length=20, choices=NatureMouvement.choices, default=NatureMouvement.ENCAISSEMENT
    )
    statut = models.CharField(
        _("Statut"), max_length=20, choices=StatutMouvement.choices, default=StatutMouvement.VALIDE
    )
    sens = models.CharField(
        _("Sens"), max_length=10, choices=SensMouvement.choices, blank=True, default=""
    )
    montant = models.DecimalField(_("Montant"), max_digits=15, decimal_places=2)
    libelle = models.CharField(_("Libellé"), max_length=255)
    reference = models.CharField(_("Référence"), max_length=100, blank=True, null=True)
    idempotency_key = models.CharField(
        _("Clé d'idempotence"),
        max_length=128,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Clé fournie par le système appelant pour éviter une double opération."),
    )
    date = models.DateTimeField(_("Date"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Créé par")
    )

    annule = models.BooleanField(_("Annulé"), default=False)
    annule_le = models.DateTimeField(_("Annulé le"), blank=True, null=True)
    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mouvements_annules",
        verbose_name=_("Annulé par"),
    )
    mouvement_parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="annulations",
        verbose_name=_("Mouvement parent"),
    )

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source = GenericForeignKey("content_type", "object_id")

    class Meta:
        verbose_name = _("Mouvement")
        verbose_name_plural = _("Mouvements")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["compte", "date"]),
            models.Index(fields=["reference"]),
            models.Index(fields=["statut"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(montant__gt=0),
                name="mouvement_montant_positif",
            ),
        ]

    def __str__(self):
        return f"{self.compte.code} - {self.nature} - {self.montant:,.0f} {self.compte.devise}"

    def save(self, *args, **kwargs):
        """Empêche l'altération d'une écriture financière déjà validée."""
        if self.pk:
            original = type(self).objects.only(
                "compte_id", "nature", "statut", "sens", "montant", "libelle", "reference",
                "idempotency_key", "content_type_id", "object_id", "created_by_id",
            ).get(pk=self.pk)
            protected_fields = (
                "compte_id", "nature", "sens", "montant", "libelle", "reference",
                "idempotency_key", "content_type_id", "object_id", "created_by_id",
            )
            protected_changed = any(
                getattr(self, field) != getattr(original, field) for field in protected_fields
            )
            if original.statut in (
                StatutMouvement.VALIDE,
                StatutMouvement.RAPPROCHE,
                StatutMouvement.ANNULE,
            ) and protected_changed:
                raise ValueError("Un mouvement validé ne peut pas être modifié; annulez-le plutôt.")
            transitions_autorisees = {
                (StatutMouvement.VALIDE, StatutMouvement.ANNULE),
                (StatutMouvement.VALIDE, StatutMouvement.RAPPROCHE),
            }
            if self.statut != original.statut and (original.statut, self.statut) not in transitions_autorisees:
                raise ValueError("La transition de statut demandée n'est pas autorisée.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.statut in (StatutMouvement.VALIDE, StatutMouvement.RAPPROCHE, StatutMouvement.ANNULE):
            raise ValueError("Un mouvement financier ne peut pas être supprimé.")
        return super().delete(*args, **kwargs)

    @property
    def est_entree(self):
        if self.sens:
            return self.sens == SensMouvement.ENTREE
        return self.nature in (
            NatureMouvement.ENCAISSEMENT,
            NatureMouvement.TRANSFERT,
            NatureMouvement.AJUSTEMENT,
            NatureMouvement.OUVERTURE,
        )

    @property
    def est_sortie(self):
        if self.sens:
            return self.sens == SensMouvement.SORTIE
        return self.nature in (
            NatureMouvement.DECAISSEMENT,
            NatureMouvement.ANNULATION,
            NatureMouvement.CLOTURE,
        )
