from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class ProviderKind(models.TextChoices):
    CASH = "CASH", _("Espèces")
    MOBILE_MONEY = "MOBILE_MONEY", _("Mobile Money")
    BANK = "BANK", _("Banque")
    PAYMENT_INSTITUTION = "PAYMENT_INSTITUTION", _("Établissement de paiement")
    OTHER = "OTHER", _("Autre")


class FinancialProvider(models.Model):
    code = models.CharField(_("Code"), max_length=80, unique=True)
    name = models.CharField(_("Nom affiché"), max_length=120)
    official_name = models.CharField(_("Nom officiel"), max_length=255, blank=True, default="")
    kind = models.CharField(_("Famille"), max_length=30, choices=ProviderKind.choices)
    country_code = models.CharField(_("Pays"), max_length=2, db_index=True)
    logo = models.CharField(_("Logo"), max_length=255, blank=True, default="")
    active = models.BooleanField(_("Actif"), default=True)
    selectable = models.BooleanField(_("Sélectionnable"), default=True)
    sort_order = models.PositiveIntegerField(_("Ordre"), default=0)
    aliases = models.JSONField(_("Alias"), default=list, blank=True)
    metadata = models.JSONField(_("Métadonnées"), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Fournisseur financier")
        verbose_name_plural = _("Fournisseurs financiers")
        ordering = ["country_code", "sort_order", "name"]
        indexes = [
            models.Index(fields=["country_code", "kind", "active", "selectable"]),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        self.name = self.name.strip()
        self.official_name = self.official_name.strip()
        self.country_code = self.country_code.strip().upper()
        if not self.code:
            raise ValidationError({"code": _("Le code est obligatoire.")})
        if not self.name:
            raise ValidationError({"name": _("Le nom affiché est obligatoire.")})
        if len(self.country_code) != 2:
            raise ValidationError({"country_code": _("Le code pays doit contenir deux lettres.")})

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.name = self.name.strip()
        self.official_name = self.official_name.strip()
        self.country_code = self.country_code.strip().upper()
        return super().save(*args, **kwargs)
