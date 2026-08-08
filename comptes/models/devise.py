from django.db import models
from django.utils.translation import gettext_lazy as _


class Devise(models.Model):
    """Référentiel des devises ISO 4217 et des devises propres à l'organisation."""

    code = models.CharField(_("Code ISO"), max_length=10, unique=True)
    nom = models.CharField(_("Nom"), max_length=100)
    code_numerique = models.CharField(_("Code numérique ISO"), max_length=3, blank=True, default="")
    decimales = models.PositiveSmallIntegerField(_("Décimales"), default=2)
    symbole = models.CharField(_("Symbole"), max_length=10, blank=True, default="")
    est_personnalisee = models.BooleanField(_("Devise personnalisée"), default=False)
    actif = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Devise")
        verbose_name_plural = _("Devises")
        ordering = ["code"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.nom = self.nom.strip()
        return super().save(*args, **kwargs)
