from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    Compte, MouvementCompte, TransfertCompte,
    JournalCompte, LigneJournalCompte,
    RapprochementBancaire, LigneRapprochement,
    ClotureCompte, HistoriqueCompte, CompteFavori, Devise, ModePaiement,
)


class MouvementCompteInline(admin.TabularInline):
    model = MouvementCompte
    extra = 0
    fields = ["nature", "statut", "montant", "libelle", "date"]
    readonly_fields = ["date"]
    show_change_link = True


class LigneJournalCompteInline(admin.TabularInline):
    model = LigneJournalCompte
    extra = 0
    fields = ["nature", "montant", "sens", "libelle"]


class LigneRapprochementInline(admin.TabularInline):
    model = LigneRapprochement
    extra = 0
    fields = ["type_ligne", "montant", "date_operation", "libelle", "pointe"]


@admin.register(Compte)
class CompteAdmin(admin.ModelAdmin):
    list_display = [
        "code", "nom", "type", "role", "devise",
        "solde_actuel", "actif", "autoriser_decouvert",
    ]
    list_filter = ["type", "role", "actif", "devise"]
    search_fields = ["code", "nom"]
    readonly_fields = ["solde_initial", "solde_actuel", "dernier_recalcul", "created_at", "updated_at"]
    inlines = [MouvementCompteInline]
    fieldsets = (
        (None, {"fields": ("code", "nom", "type", "role")}),
        (_("Devise"), {"fields": ("devise", "taux_change", "devise_reference")}),
        (_("Solde"), {"fields": ("solde_initial", "solde_actuel", "dernier_recalcul")}),
        (_("Découvert"), {"fields": ("autoriser_decouvert", "limite_decouvert")}),
        (_("Statut"), {"fields": ("actif", "date_ouverture", "date_fermeture")}),
        (_("Comptabilité"), {"fields": ("compte_comptable_code",)}),
        (_("Dates"), {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Devise)
class DeviseAdmin(admin.ModelAdmin):
    list_display = ["code", "nom", "symbole", "decimales", "est_personnalisee", "actif"]
    list_filter = ["est_personnalisee", "actif"]
    search_fields = ["code", "nom", "symbole"]


@admin.register(ModePaiement)
class ModePaiementAdmin(admin.ModelAdmin):
    list_display = ["code", "libelle", "actif"]
    list_filter = ["actif"]
    search_fields = ["code", "libelle"]
    filter_horizontal = ["comptes"]


@admin.register(MouvementCompte)
class MouvementCompteAdmin(admin.ModelAdmin):
    list_display = ["compte", "nature", "statut", "montant", "libelle", "date", "created_by"]
    list_filter = ["nature", "statut", "date"]
    search_fields = ["libelle", "reference"]
    autocomplete_fields = ["compte", "created_by", "annule_par", "mouvement_parent"]
    readonly_fields = ["date"]


@admin.register(TransfertCompte)
class TransfertCompteAdmin(admin.ModelAdmin):
    list_display = ["source", "destination", "montant", "reference", "date", "valide_par"]
    search_fields = ["reference"]
    autocomplete_fields = ["source", "destination", "valide_par"]
    readonly_fields = ["date"]


@admin.register(JournalCompte)
class JournalCompteAdmin(admin.ModelAdmin):
    list_display = [
        "compte", "date_journal", "solde_ouverture",
        "total_entrees", "total_sorties", "solde_theorique",
        "solde_reel", "ecart", "cloture",
    ]
    list_filter = ["cloture", "date_journal"]
    # Requis par LigneJournalCompteAdmin.autocomplete_fields : sans cela
    # Django refuse de demarrer (admin.E040).
    search_fields = ["compte__code", "compte__nom"]
    autocomplete_fields = ["compte"]
    readonly_fields = [
        "date_journal", "solde_ouverture", "total_entrees",
        "total_sorties", "solde_theorique", "solde_reel", "ecart",
    ]
    inlines = [LigneJournalCompteInline]


@admin.register(LigneJournalCompte)
class LigneJournalCompteAdmin(admin.ModelAdmin):
    list_display = ["journal", "nature", "montant", "sens", "libelle"]
    autocomplete_fields = ["journal"]


@admin.register(RapprochementBancaire)
class RapprochementBancaireAdmin(admin.ModelAdmin):
    list_display = ["compte", "date_debut", "date_fin", "solde_releve", "solde_comptable", "ecart", "statut"]
    list_filter = ["statut"]
    autocomplete_fields = ["compte"]
    readonly_fields = ["ecart"]
    inlines = [LigneRapprochementInline]


@admin.register(ClotureCompte)
class ClotureCompteAdmin(admin.ModelAdmin):
    list_display = ["compte", "periode", "date_cloture", "solde_avant", "solde_apres", "ecart"]
    list_filter = ["periode", "date_cloture"]
    autocomplete_fields = ["compte", "cloture_par"]


@admin.register(HistoriqueCompte)
class HistoriqueCompteAdmin(admin.ModelAdmin):
    list_display = ["compte", "type_changement", "created_at", "modifie_par"]
    list_filter = ["type_changement"]
    autocomplete_fields = ["compte", "modifie_par"]
    readonly_fields = ["created_at"]


@admin.register(CompteFavori)
class CompteFavoriAdmin(admin.ModelAdmin):
    list_display = ["compte", "utilisateur", "is_defaut", "ordre"]
    list_filter = ["is_defaut"]
    autocomplete_fields = ["compte", "utilisateur"]
