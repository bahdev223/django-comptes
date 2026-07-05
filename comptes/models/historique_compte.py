from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .compte import Compte


class TypeChangement(models.TextChoices):
    NOM = "NOM", _("Changement de nom")
    TYPE = "TYPE", _("Changement de type")
    ROLE = "ROLE", _("Changement de rôle")
    ACTIVATION = "ACTIVATION", _("Activation du compte")
    DESACTIVATION = "DESACTIVATION", _("Désactivation du compte")
    DECOUVERT = "DECOUVERT", _("Modification du découvert")
    LIMITE = "LIMITE", _("Modification de la limite")
    DEVISE = "DEVISE", _("Changement de devise")
    FERMETURE = "FERMETURE", _("Fermeture du compte")
    RECALCUL = "RECALCUL", _("Recalcul du solde")
    AUTRE = "AUTRE", _("Autre")


class HistoriqueCompte(models.Model):
    compte = models.ForeignKey(
        Compte,
        on_delete=models.CASCADE,
        related_name="historique",
        verbose_name=_("Compte"),
    )
    type_changement = models.CharField(
        _("Type de changement"), max_length=20, choices=TypeChangement.choices
    )
    ancienne_valeur = models.TextField(_("Ancienne valeur"), blank=True, default="")
    nouvelle_valeur = models.TextField(_("Nouvelle valeur"), blank=True, default="")
    commentaire = models.TextField(_("Commentaire"), blank=True, default="")
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Modifié par"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Historique du compte")
        verbose_name_plural = _("Historiques des comptes")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.compte.nom} - {self.get_type_changement_display()} - {self.created_at:%d/%m/%Y %H:%M}"
