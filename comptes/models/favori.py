from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .compte import Compte


class CompteFavori(models.Model):
    compte = models.ForeignKey(
        Compte,
        on_delete=models.CASCADE,
        related_name="favoris",
        verbose_name=_("Compte"),
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comptes_favoris",
        verbose_name=_("Utilisateur"),
    )
    ordre = models.PositiveIntegerField(_("Ordre d'affichage"), default=0)
    is_defaut = models.BooleanField(
        _("Compte par défaut"),
        default=False,
        help_text=_("Proposé par défaut lors d'un encaissement"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Compte favori")
        verbose_name_plural = _("Comptes favoris")
        unique_together = ["compte", "utilisateur"]
        ordering = ["ordre", "compte__nom"]

    def __str__(self):
        return f"{self.compte.nom} (favori de {self.utilisateur})"
