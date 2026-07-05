from django.db import models
from django.utils.translation import gettext_lazy as _

from .compte import Compte
from .mouvement_compte import MouvementCompte


class StatutRapprochement(models.TextChoices):
    EN_COURS = "EN_COURS", _("En cours")
    PARTIEL = "PARTIEL", _("Partiel")
    EQUILIBRE = "EQUILIBRE", _("Équilibré")
    ECART = "ECART", _("Écart constaté")


class RapprochementBancaire(models.Model):
    compte = models.ForeignKey(
        Compte,
        on_delete=models.CASCADE,
        related_name="rapprochements",
        verbose_name=_("Compte"),
    )
    date_debut = models.DateField(_("Date début"))
    date_fin = models.DateField(_("Date fin"))
    date_releve = models.DateField(_("Date du relevé"))
    solde_releve = models.DecimalField(_("Solde relevé"), max_digits=15, decimal_places=2)
    solde_comptable = models.DecimalField(
        _("Solde comptable"), max_digits=15, decimal_places=2
    )
    ecart = models.DecimalField(_("Écart"), max_digits=15, decimal_places=2, default=0)
    statut = models.CharField(
        _("Statut"),
        max_length=20,
        choices=StatutRapprochement.choices,
        default=StatutRapprochement.EN_COURS,
    )
    commentaire = models.TextField(_("Commentaire"), blank=True, default="")
    date_validation = models.DateTimeField(_("Date de validation"), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Rapprochement bancaire")
        verbose_name_plural = _("Rapprochements bancaires")
        ordering = ["-date_fin"]

    def __str__(self):
        return f"{self.compte.nom} - {self.date_debut} → {self.date_fin}"


class LigneRapprochement(models.Model):
    rapprochement = models.ForeignKey(
        RapprochementBancaire,
        on_delete=models.CASCADE,
        related_name="lignes",
        verbose_name=_("Rapprochement"),
    )
    mouvement = models.ForeignKey(
        MouvementCompte,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lignes_rapprochement",
        verbose_name=_("Mouvement"),
    )
    type_ligne = models.CharField(
        _("Type"), max_length=10, choices=[("RELEVE", "Relevé"), ("COMPTABLE", "Comptable"), ("ECART", "Écart")]
    )
    montant = models.DecimalField(_("Montant"), max_digits=15, decimal_places=2)
    date_operation = models.DateField(_("Date opération"))
    libelle = models.CharField(_("Libellé"), max_length=255)
    pointe = models.BooleanField(_("Pointé"), default=False)
    commentaire = models.CharField(_("Commentaire"), max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("Ligne de rapprochement")
        verbose_name_plural = _("Lignes de rapprochement")

    def __str__(self):
        return f"{self.rapprochement} - {self.libelle}"
