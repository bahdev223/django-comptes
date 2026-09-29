from django.urls import path

from . import views

app_name = "comptes"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("comptes/", views.liste_comptes, name="liste_comptes"),
    path("comptes/ajouter/", views.ajouter_compte, name="ajouter_compte"),
    path("comptes/<int:compte_id>/", views.detail_compte, name="detail_compte"),
    path("comptes/<int:compte_id>/modifier/", views.modifier_compte, name="modifier_compte"),
    path("comptes/<int:compte_id>/cloturer/", views.cloturer_compte, name="cloturer_compte"),
    path("comptes/<int:compte_id>/journal/", views.journal_consulter, name="journal_consulter"),
    path("mouvements/", views.liste_mouvements, name="liste_mouvements"),
    path("mouvements/encaisser/", views.mouvement_encaisser, name="mouvement_encaisser"),
    path("mouvements/decaisser/", views.mouvement_decaisser, name="mouvement_decaisser"),
    path("transferts/", views.transfert_effectuer, name="transfert_effectuer"),
    path("transferts/liste/", views.liste_transferts, name="liste_transferts"),
    path("rapprochement/", views.rapprochement_liste, name="rapprochement_liste"),
    path(
        "rapprochement/initialiser/",
        views.rapprochement_initialiser,
        name="rapprochement_initialiser",
    ),
    path(
        "rapprochement/<int:rapprochement_id>/",
        views.rapprochement_detail,
        name="rapprochement_detail",
    ),
    path(
        "rapprochement/<int:rapprochement_id>/lignes/<int:ligne_id>/pointer/",
        views.rapprochement_pointer,
        name="rapprochement_pointer",
    ),
    path(
        "rapprochement/<int:rapprochement_id>/lignes/<int:ligne_id>/depointer/",
        views.rapprochement_depointer,
        name="rapprochement_depointer",
    ),
    path(
        "rapprochement/<int:rapprochement_id>/lignes-releve/ajouter/",
        views.rapprochement_ajouter_ligne_releve,
        name="rapprochement_ajouter_ligne_releve",
    ),
    path(
        "rapprochement/<int:rapprochement_id>/valider/",
        views.rapprochement_valider,
        name="rapprochement_valider",
    ),
]
