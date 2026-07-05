from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
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


class MouvementCompte(models.Model):
    compte = models.ForeignKey(
        Compte, on_delete=models.CASCADE, related_name="mouvements", verbose_name=_("Compte")
    )
    nature = models.CharField(
        _("Nature"), max_length=20, choices=NatureMouvement.choices, default=NatureMouvement.ENCAISSEMENT
    )
    statut = models.CharField(
        _("Statut"), max_length=20, choices=StatutMouvement.choices, default=StatutMouvement.VALIDE
    )
    montant = models.DecimalField(_("Montant"), max_digits=15, decimal_places=2)
    libelle = models.CharField(_("Libellé"), max_length=255)
    reference = models.CharField(_("Référence"), max_length=100, blank=True, null=True)
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

    def __str__(self):
        return f"{self.compte.code} - {self.nature} - {self.montant:,.0f} {self.compte.devise}"

    @property
    def est_entree(self):
        return self.nature in (
            NatureMouvement.ENCAISSEMENT,
            NatureMouvement.TRANSFERT,
            NatureMouvement.AJUSTEMENT,
            NatureMouvement.OUVERTURE,
        )

    @property
    def est_sortie(self):
        return self.nature in (
            NatureMouvement.DECAISSEMENT,
            NatureMouvement.ANNULATION,
            NatureMouvement.CLOTURE,
        )
