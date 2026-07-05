from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .compte import Compte


class PeriodeCloture(models.TextChoices):
    QUOTIDIENNE = "QUOTIDIENNE", _("Quotidienne")
    HEBDOMADAIRE = "HEBDOMADAIRE", _("Hebdomadaire")
    MENSUELLE = "MENSUELLE", _("Mensuelle")
    TRIMESTRIELLE = "TRIMESTRIELLE", _("Trimestrielle")
    ANNUELLE = "ANNUELLE", _("Annuelle")


class ClotureCompte(models.Model):
    compte = models.ForeignKey(
        Compte, on_delete=models.CASCADE, related_name="clotures", verbose_name=_("Compte")
    )
    periode = models.CharField(
        _("Période"), max_length=20, choices=PeriodeCloture.choices, default=PeriodeCloture.QUOTIDIENNE
    )
    date_cloture = models.DateField(_("Date de clôture"))
    solde_avant = models.DecimalField(_("Solde avant clôture"), max_digits=15, decimal_places=2)
    solde_apres = models.DecimalField(_("Solde après clôture"), max_digits=15, decimal_places=2)
    ecart = models.DecimalField(_("Écart"), max_digits=15, decimal_places=2, default=0)
    commentaire = models.TextField(_("Commentaire"), blank=True, default="")
    cloture_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Clôturé par"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Clôture de compte")
        verbose_name_plural = _("Clôtures de comptes")
        unique_together = ["compte", "periode", "date_cloture"]
        ordering = ["-date_cloture"]

    def __str__(self):
        return f"{self.compte.nom} - {self.get_periode_display()} - {self.date_cloture}"
