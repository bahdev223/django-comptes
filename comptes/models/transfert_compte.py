from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from .compte import Compte
from .immutable import ImmutableFinancialManager


class TransfertCompte(models.Model):
    objects = ImmutableFinancialManager()

    source = models.ForeignKey(
        Compte, on_delete=models.PROTECT, related_name="transferts_sortants", verbose_name=_("Source")
    )
    destination = models.ForeignKey(
        Compte,
        on_delete=models.PROTECT,
        related_name="transferts_entrants",
        verbose_name=_("Destination"),
    )
    montant = models.DecimalField(_("Montant"), max_digits=15, decimal_places=2)
    reference = models.CharField(_("Référence"), max_length=100, unique=True)
    entreprise_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    idempotency_key = models.CharField(
        _("Clé d'idempotence"), max_length=128, blank=True, null=True
    )
    payload_hash = models.CharField(max_length=128, blank=True, default="")
    source_system = models.CharField(max_length=80, blank=True, default="")
    source_type = models.CharField(max_length=80, blank=True, default="")
    external_source_id = models.CharField(max_length=120, blank=True, default="")
    source_reference = models.CharField(max_length=120, blank=True, default="")
    date = models.DateTimeField(_("Date"), auto_now_add=True)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Validé par")
    )
    notes = models.TextField(_("Notes"), blank=True, default="")

    class Meta:
        verbose_name = _("Transfert")
        verbose_name_plural = _("Transferts")
        ordering = ["-date"]
        constraints = [
            models.CheckConstraint(condition=Q(montant__gt=0), name="transfert_montant_positif"),
            models.CheckConstraint(
                condition=~Q(source=F("destination")),
                name="transfert_comptes_distincts",
            ),
            models.UniqueConstraint(
                fields=["entreprise_id", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False) & ~Q(idempotency_key=""),
                name="transfert_idempotence_par_entreprise",
            ),
        ]

    def __str__(self):
        return f"{self.source.code} → {self.destination.code} : {self.montant:,.0f}"

    def save(self, *args, **kwargs):
        if self.source_id and not self.entreprise_id:
            self.entreprise_id = self.source.entreprise_id

        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            protected = (
                "source_id", "destination_id", "montant", "reference", "entreprise_id",
                "idempotency_key", "payload_hash", "source_system", "source_type",
                "external_source_id", "source_reference", "valide_par_id",
            )
            if any(getattr(self, field) != getattr(original, field) for field in protected):
                raise ValueError("Un transfert validé ne peut pas être modifié.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Un transfert financier ne peut pas être supprimé.")
