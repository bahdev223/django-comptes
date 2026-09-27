from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class ModePaiement(models.Model):
    """Mode de paiement configurable par l'organisation.

    Les valeurs ne sont volontairement pas définies sous forme de ``choices`` :
    chaque organisation crée uniquement les modes qu'elle accepte. Un mode peut
    être encaissé sur plusieurs comptes financiers.
    """

    code = models.CharField(
        _("Code"),
        max_length=50,
        help_text=_("Identifiant métier libre, par exemple ESPECES ou ORANGE_MONEY."),
    )
    entreprise_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    libelle = models.CharField(_("Libellé"), max_length=100)
    actif = models.BooleanField(_("Actif"), default=True)
    comptes = models.ManyToManyField(
        "Compte",
        blank=True,
        through="ModePaiementCompte",
        related_name="modes_paiement",
        verbose_name=_("Comptes liés"),
        help_text=_("Comptes sur lesquels ce mode de paiement peut être encaissé."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Mode de paiement")
        verbose_name_plural = _("Modes de paiement")
        ordering = ["libelle", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entreprise_id", "code"],
                name="mode_paiement_unique_par_entreprise",
            ),
        ]

    def __str__(self):
        return self.libelle

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        self.libelle = self.libelle.strip()
        if not self.code:
            raise ValidationError({"code": _("Le code est obligatoire.")})
        if not self.libelle:
            raise ValidationError({"libelle": _("Le libellé est obligatoire.")})

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.libelle = self.libelle.strip()
        return super().save(*args, **kwargs)


class ModePaiementCompte(models.Model):
    mode_paiement = models.ForeignKey(
        ModePaiement,
        on_delete=models.CASCADE,
        related_name="liens_comptes",
        verbose_name=_("Mode de paiement"),
    )
    compte = models.ForeignKey(
        "Compte",
        on_delete=models.CASCADE,
        related_name="liens_modes_paiement",
        verbose_name=_("Compte"),
    )
    priorite = models.PositiveIntegerField(_("Priorité"), default=0)
    actif = models.BooleanField(_("Actif"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Lien mode de paiement / compte")
        verbose_name_plural = _("Liens modes de paiement / comptes")
        ordering = ["priorite", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["mode_paiement", "compte"],
                name="mode_paiement_compte_unique",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.mode_paiement_id
            and self.compte_id
            and self.mode_paiement.entreprise_id != self.compte.entreprise_id
        ):
            raise ValidationError(
                _("Un mode de paiement ne peut pas être lié à un compte d'une autre entreprise.")
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
