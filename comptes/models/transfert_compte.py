from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .compte import Compte


class TransfertCompte(models.Model):
    source = models.ForeignKey(
        Compte, on_delete=models.CASCADE, related_name="transferts_sortants", verbose_name=_("Source")
    )
    destination = models.ForeignKey(
        Compte,
        on_delete=models.CASCADE,
        related_name="transferts_entrants",
        verbose_name=_("Destination"),
    )
    montant = models.DecimalField(_("Montant"), max_digits=15, decimal_places=2)
    reference = models.CharField(_("Référence"), max_length=100, unique=True)
    date = models.DateTimeField(_("Date"), auto_now_add=True)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Validé par")
    )
    notes = models.TextField(_("Notes"), blank=True, default="")

    class Meta:
        verbose_name = _("Transfert")
        verbose_name_plural = _("Transferts")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.source.code} → {self.destination.code} : {self.montant:,.0f}"
