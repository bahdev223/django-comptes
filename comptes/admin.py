from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    ClotureCompte,
    Compte,
    CompteFavori,
    Devise,
    FinancialProvider,
    HistoriqueCompte,
    JournalCompte,
    LigneJournalCompte,
    LigneRapprochement,
    ModePaiement,
    MouvementCompte,
    RapprochementBancaire,
    TransfertCompte,
)

admin.site.site_header = "Finance · Administration"
admin.site.site_title = "Finance"
admin.site.index_title = "Comptes, trésorerie et référentiels"


class FinanceAdminMixin:
    class Media:
        css = {"all": ("comptes/admin.css",)}


class ReadOnlyFinancialAdmin(FinanceAdminMixin, admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


class MouvementCompteInline(admin.TabularInline):
    model = MouvementCompte
    extra = 0
    fields = ["nature", "statut", "montant", "libelle", "date"]
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class LigneJournalCompteInline(admin.TabularInline):
    model = LigneJournalCompte
    extra = 0
    fields = ["nature", "montant", "sens", "libelle"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class LigneRapprochementInline(admin.TabularInline):
    model = LigneRapprochement
    extra = 0
    fields = ["type_ligne", "montant", "date_operation", "libelle", "pointe"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Compte)
class CompteAdmin(FinanceAdminMixin, admin.ModelAdmin):
    list_display = [
        "code", "nom", "provider", "type", "role", "devise",
        "solde_actuel", "accepte_ventes", "par_defaut", "actif",
    ]
    list_filter = [
        "type", "role", "provider__kind", "accepte_ventes",
        "par_defaut", "actif", "devise",
    ]
    search_fields = ["code", "nom", "provider__code", "provider__name", "identifiant"]
    readonly_fields = [
        "solde_initial", "solde_actuel", "dernier_recalcul",
        "created_at", "updated_at", "entreprise_id",
    ]
    list_select_related = ["provider", "devise"]
    inlines = [MouvementCompteInline]
    fieldsets = (
        (_("Identité"), {"fields": ("code", "nom", "provider", "identifiant", "type", "role")}),
        (_("Devise"), {"fields": ("devise", "taux_change", "devise_reference")}),
        (_("Solde"), {"fields": ("solde_initial", "solde_actuel", "dernier_recalcul")}),
        (_("Usage"), {"fields": ("accepte_ventes", "par_defaut")}),
        (_("Découvert"), {"fields": ("autoriser_decouvert", "limite_decouvert")}),
        (_("Statut"), {"fields": ("actif", "date_ouverture", "date_fermeture")}),
        (_("Comptabilité"), {"fields": ("compte_comptable_code",)}),
        (_("Technique"), {"fields": ("entreprise_id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(FinancialProvider)
class FinancialProviderAdmin(FinanceAdminMixin, admin.ModelAdmin):
    list_display = [
        "code", "name", "official_name", "kind", "country_code",
        "active", "selectable", "sort_order",
    ]
    list_filter = ["country_code", "kind", "active", "selectable"]
    search_fields = ["code", "name", "official_name"]
    ordering = ["country_code", "sort_order", "name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Devise)
class DeviseAdmin(FinanceAdminMixin, admin.ModelAdmin):
    list_display = ["code", "nom", "symbole", "decimales", "est_personnalisee", "actif"]
    list_filter = ["est_personnalisee", "actif"]
    search_fields = ["code", "nom", "symbole"]


@admin.register(ModePaiement)
class ModePaiementAdmin(FinanceAdminMixin, admin.ModelAdmin):
    list_display = ["code", "libelle", "entreprise_id", "actif"]
    list_filter = ["actif", "entreprise_id"]
    search_fields = ["code", "libelle", "entreprise_id"]
    readonly_fields = ["entreprise_id", "created_at", "updated_at"]


@admin.register(MouvementCompte)
class MouvementCompteAdmin(ReadOnlyFinancialAdmin):
    list_display = ["compte", "nature", "statut", "sens", "montant", "date", "created_by"]
    list_filter = ["nature", "statut", "sens", "date", "entreprise_id"]
    search_fields = ["libelle", "reference", "source_reference", "idempotency_key"]
    list_select_related = ["compte", "created_by"]


@admin.register(TransfertCompte)
class TransfertCompteAdmin(ReadOnlyFinancialAdmin):
    list_display = ["source", "destination", "montant", "reference", "date", "valide_par"]
    list_filter = ["entreprise_id", "date"]
    search_fields = ["reference", "source_reference", "idempotency_key"]
    list_select_related = ["source", "destination", "valide_par"]


@admin.register(JournalCompte)
class JournalCompteAdmin(ReadOnlyFinancialAdmin):
    list_display = [
        "compte", "date_journal", "solde_ouverture",
        "total_entrees", "total_sorties", "solde_theorique",
        "solde_reel", "ecart", "cloture",
    ]
    list_filter = ["cloture", "date_journal"]
    search_fields = ["compte__code", "compte__nom"]
    list_select_related = ["compte"]
    inlines = [LigneJournalCompteInline]


@admin.register(LigneJournalCompte)
class LigneJournalCompteAdmin(ReadOnlyFinancialAdmin):
    list_display = ["journal", "nature", "montant", "sens", "libelle"]
    search_fields = ["libelle", "reference"]


@admin.register(RapprochementBancaire)
class RapprochementBancaireAdmin(ReadOnlyFinancialAdmin):
    list_display = [
        "compte", "date_debut", "date_fin", "solde_releve",
        "solde_comptable", "ecart", "statut",
    ]
    list_filter = ["statut", "date_fin"]
    search_fields = ["compte__code", "compte__nom"]
    list_select_related = ["compte"]
    inlines = [LigneRapprochementInline]


@admin.register(ClotureCompte)
class ClotureCompteAdmin(ReadOnlyFinancialAdmin):
    list_display = ["compte", "periode", "date_cloture", "solde_avant", "solde_apres", "ecart"]
    list_filter = ["periode", "date_cloture"]
    search_fields = ["compte__code", "compte__nom"]
    list_select_related = ["compte", "cloture_par"]


@admin.register(HistoriqueCompte)
class HistoriqueCompteAdmin(ReadOnlyFinancialAdmin):
    list_display = ["compte", "type_changement", "created_at", "modifie_par"]
    list_filter = ["type_changement", "created_at"]
    search_fields = ["compte__code", "compte__nom", "commentaire"]
    list_select_related = ["compte", "modifie_par"]


@admin.register(CompteFavori)
class CompteFavoriAdmin(FinanceAdminMixin, admin.ModelAdmin):
    list_display = ["compte", "utilisateur", "is_defaut", "ordre"]
    list_filter = ["is_defaut"]
    search_fields = ["compte__code", "compte__nom", "utilisateur__username"]
