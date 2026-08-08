from django.core.exceptions import ValidationError
from django.db import models
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
        unique=True,
        help_text=_("Identifiant métier libre, par exemple ESPECES ou ORANGE_MONEY."),
    )
    libelle = models.CharField(_("Libellé"), max_length=100)
    actif = models.BooleanField(_("Actif"), default=True)
    comptes = models.ManyToManyField(
        "Compte",
        blank=True,
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
