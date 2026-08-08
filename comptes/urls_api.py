from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.views import (
    CompteViewSet, ModePaiementViewSet, MouvementCompteViewSet, TransfertCompteViewSet,
    JournalCompteViewSet, RapprochementBancaireViewSet, ClotureCompteViewSet,
)

router = DefaultRouter()
router.register(r"comptes", CompteViewSet)
router.register(r"modes-paiement", ModePaiementViewSet)
router.register(r"mouvements", MouvementCompteViewSet)
router.register(r"transferts", TransfertCompteViewSet)
router.register(r"journaux", JournalCompteViewSet)
router.register(r"rapprochements", RapprochementBancaireViewSet)
router.register(r"clotures", ClotureCompteViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
]
