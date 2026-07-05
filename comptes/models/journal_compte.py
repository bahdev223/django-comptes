from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from .compte import Compte


class JournalCompte(models.Model):
    compte = models.ForeignKey(
        Compte, on_delete=models.CASCADE, related_name="journaux", verbose_name=_("Compte")
    )
    date_journal = models.DateField(_("Date du journal"), auto_now_add=True)
    solde_ouverture = models.DecimalField(
        _("Solde d'ouverture"), max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    total_entrees = models.DecimalField(
        _("Total entrées"), max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    total_sorties = models.DecimalField(
        _("Total sorties"), max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    solde_theorique = models.DecimalField(
        _("Solde théorique"), max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    solde_reel = models.DecimalField(
        _("Solde réel"), max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    ecart = models.DecimalField(
        _("Écart"), max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    cloture = models.BooleanField(_("Clôturé"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Journal de compte")
        verbose_name_plural = _("Journaux de comptes")
        unique_together = ["compte", "date_journal"]
        ordering = ["-date_journal"]

    def __str__(self):
        return f"{self.compte.nom} - {self.date_journal}"


class LigneJournalCompte(models.Model):
    journal = models.ForeignKey(
        JournalCompte, on_delete=models.CASCADE, related_name="lignes", verbose_name=_("Journal")
    )
    type_operation = models.CharField(_("Type d'opération"), max_length=50)
    nature = models.CharField(_("Nature"), max_length=20, blank=True, default="")
    montant = models.DecimalField(_("Montant"), max_digits=15, decimal_places=2)
    sens = models.CharField(_("Sens"), max_length=10)
    reference = models.CharField(_("Référence"), max_length=100, blank=True, null=True)
    libelle = models.CharField(_("Libellé"), max_length=255)

    class Meta:
        verbose_name = _("Ligne de journal")
        verbose_name_plural = _("Lignes de journal")

    def __str__(self):
        return f"{self.journal.compte.nom} - {self.sens} - {self.montant:,.0f}"
