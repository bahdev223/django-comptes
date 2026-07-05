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
    path("transferts/", views.transfert_effectuer, name="transfert_effectuer"),
    path("transferts/liste/", views.liste_transferts, name="liste_transferts"),
    path("rapprochement/", views.rapprochement_liste, name="rapprochement_liste"),
    path("rapprochement/<int:rapprochement_id>/", views.rapprochement_detail, name="rapprochement_detail"),
    path("rapprochement/initialiser/", views.rapprochement_initialiser, name="rapprochement_initialiser"),
]
