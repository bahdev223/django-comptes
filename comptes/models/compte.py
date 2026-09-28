from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .managers import ComptesManager
from ..defaults import default_currency


class TypeCompte(models.TextChoices):
    ESPECES = "ESPECES", _("Espèces")
    BANQUE = "BANQUE", _("Compte bancaire")
    MOBILE_MONEY = "MOBILE_MONEY", _("Mobile Money")
    CARTE = "CARTE", _("Carte de crédit/débit")
    PORTEFEUILLE_NUMERIQUE = "PORTEFEUILLE_NUMERIQUE", _("Portefeuille numérique")
    AUTRE = "AUTRE", _("Autre")


class RoleCompte(models.TextChoices):
    PRINCIPAL = "PRINCIPAL", _("Principal")
    POINT_VENTE = "POINT_VENTE", _("Point de vente")
    CAISSE = "CAISSE", _("Caisse")
    EPARGNE = "EPARGNE", _("Épargne")
    ENCAISSEMENT = "ENCAISSEMENT", _("Encaissement")
    DECAISSEMENT = "DECAISSEMENT", _("Décaissement")


class Compte(models.Model):
    code = models.CharField(_("Code"), max_length=20)
    nom = models.CharField(_("Nom"), max_length=200)
    provider = models.ForeignKey(
        "FinancialProvider",
        on_delete=models.PROTECT,
        related_name="comptes",
        verbose_name=_("Fournisseur financier"),
        blank=True,
        null=True,
    )
    identifiant = models.CharField(
        _("Identifiant du compte"),
        max_length=120,
        blank=True,
        default="",
        help_text=_("Numéro de téléphone, numéro de compte bancaire ou libellé libre."),
    )
    type = models.CharField(
        _("Type"), max_length=30, choices=TypeCompte.choices, default=TypeCompte.ESPECES
    )
    role = models.CharField(
        _("Rôle"), max_length=20, choices=RoleCompte.choices, blank=True, null=True
    )
    devise = models.ForeignKey(
        "Devise",
        to_field="code",
        db_column="devise",
        on_delete=models.PROTECT,
        related_name="comptes",
        verbose_name=_("Devise"),
        default=default_currency,
    )
    taux_change = models.DecimalField(
        _("Taux de change"), max_digits=12, decimal_places=6, default=Decimal("1.000000")
    )
    devise_reference = models.CharField(
        _("Devise de référence"), max_length=10, blank=True, default=""
    )

    solde_actuel = models.DecimalField(
        _("Solde actuel"), max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    solde_initial = models.DecimalField(
        _("Solde initial"), max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    accepte_ventes = models.BooleanField(
        _("Accepte les ventes"),
        default=True,
        help_text=_("Compte proposé lors d'un encaissement de vente."),
    )
    par_defaut = models.BooleanField(_("Compte par défaut"), default=False)
    dernier_recalcul = models.DateTimeField(
        _("Dernier recalcul du solde"), blank=True, null=True
    )
    actif = models.BooleanField(_("Actif"), default=True)
    autoriser_decouvert = models.BooleanField(_("Autoriser le découvert"), default=False)
    limite_decouvert = models.DecimalField(
        _("Limite de découvert"), max_digits=15, decimal_places=2, default=Decimal("0.00")
    )

    date_ouverture = models.DateField(_("Date d'ouverture"), auto_now_add=True)
    date_fermeture = models.DateField(_("Date de fermeture"), blank=True, null=True)

    compte_comptable_code = models.CharField(
        _("Code compte comptable SYSCOHADA"),
        max_length=20,
        blank=True,
        default="",
        help_text=_("Code du plan comptable (ex: 5711, 5211, 5811). Lien symbolique, pas une FK."),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ComptesManager()

    entreprise_id = models.CharField(max_length=255, blank=True, default="", db_index=True)

    class Meta:
        unique_together = [["entreprise_id", "code"]]
        verbose_name = _("Compte financier")
        verbose_name_plural = _("Comptes financiers")
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entreprise_id"],
                condition=Q(par_defaut=True),
                name="compte_defaut_unique_par_entreprise",
            ),
        ]
        permissions = [
            ("encaisser", "Peut encaisser sur un compte"),
            ("decaisser", "Peut décaisser depuis un compte"),
            ("transferer", "Peut transférer entre comptes"),
            ("annuler", "Peut annuler un mouvement"),
            ("cloturer", "Peut clôturer un compte"),
            ("rapprocher", "Peut rapprocher un compte"),
        ]

    def __str__(self):
        return f"{self.code} - {self.nom}"

    def _validate_provider_type(self):
        if not self.provider_id:
            return
        from .financial_provider import ProviderKind

        expected = {
            ProviderKind.CASH: TypeCompte.ESPECES,
            ProviderKind.BANK: TypeCompte.BANQUE,
            ProviderKind.MOBILE_MONEY: TypeCompte.MOBILE_MONEY,
            ProviderKind.PAYMENT_INSTITUTION: TypeCompte.AUTRE,
        }.get(self.provider.kind)

        if expected and self.type != expected:
            raise ValidationError({
                "type": _(
                    "Le type du compte est incompatible avec le fournisseur financier sélectionné."
                )
            })

    def clean(self):
        super().clean()
        self._validate_provider_type()

    def save(self, *args, **kwargs):
        if self._state.adding and self.solde_initial == Decimal("0.00") and self.solde_actuel != Decimal("0.00"):
            self.solde_initial = self.solde_actuel
        self._validate_provider_type()
        return super().save(*args, **kwargs)

    @property
    def solde_disponible(self):
        if self.autoriser_decouvert:
            return self.solde_actuel + self.limite_decouvert
        return self.solde_actuel

    @property
    def est_a_decouvert(self):
        return self.autoriser_decouvert and self.solde_actuel < 0

    @property
    def est_banque(self):
        return self.type == TypeCompte.BANQUE

    @property
    def est_caisse(self):
        return self.type == TypeCompte.ESPECES

    @property
    def est_mobile_money(self):
        return self.type == TypeCompte.MOBILE_MONEY
