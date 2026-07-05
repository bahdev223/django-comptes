from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import (
    Compte, MouvementCompte, TransfertCompte,
    JournalCompte, RapprochementBancaire, ClotureCompte,
)
from ..services import (
    MouvementCompteService, TransfertCompteService,
    ClotureCompteService, CompteService,
)
from ..selectors import DashboardSelector, MouvementSelector
from .serializers import (
    CompteSerializer, MouvementCompteSerializer,
    TransfertCompteSerializer, JournalCompteSerializer,
    RapprochementBancaireSerializer, ClotureCompteSerializer,
)


class CompteViewSet(viewsets.ModelViewSet):
    queryset = Compte.objects.all()
    serializer_class = CompteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["type", "role", "actif", "devise"]
    search_fields = ["code", "nom"]

    @action(detail=True, methods=["post"])
    def recalculer_solde(self, request, pk=None):
        compte = self.get_object()
        nouveau_solde = CompteService.recalculer_solde(compte)
        return Response({"solde_actuel": nouveau_solde})

    @action(detail=True, methods=["get"])
    def historique(self, request, pk=None):
        compte = self.get_object()
        h = compte.historique.all().order_by("-created_at")[:50]
        data = [
            {
                "date": x.created_at.isoformat(),
                "type": x.type_changement,
                "ancien": x.ancienne_valeur,
                "nouveau": x.nouvelle_valeur,
            }
            for x in h
        ]
        return Response(data)

    @action(detail=False, methods=["get"])
    def synthese(self, request):
        selector = DashboardSelector()
        return Response(selector.synthese_globale())


class MouvementCompteViewSet(viewsets.ModelViewSet):
    queryset = MouvementCompte.objects.select_related("compte", "created_by")
    serializer_class = MouvementCompteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["compte", "nature", "statut"]
    search_fields = ["libelle", "reference"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["post"])
    def encaisser(self, request):
        compte = Compte.objects.get(id=request.data["compte_id"])
        mvt = MouvementCompteService.encaisser(
            compte=compte,
            montant=request.data["montant"],
            libelle=request.data.get("libelle", ""),
            user=request.user,
            reference=request.data.get("reference", ""),
        )
        return Response(MouvementCompteSerializer(mvt).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def decaisser(self, request):
        compte = Compte.objects.get(id=request.data["compte_id"])
        mvt = MouvementCompteService.decaisser(
            compte=compte,
            montant=request.data["montant"],
            libelle=request.data.get("libelle", ""),
            user=request.user,
            reference=request.data.get("reference", ""),
        )
        return Response(MouvementCompteSerializer(mvt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        mvt = self.get_object()
        annulation = MouvementCompteService.annuler(
            mvt, user=request.user, raison=request.data.get("raison", "")
        )
        return Response(MouvementCompteSerializer(annulation).data)


class TransfertCompteViewSet(viewsets.ModelViewSet):
    queryset = TransfertCompte.objects.select_related("source", "destination")
    serializer_class = TransfertCompteSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def transferer(self, request):
        source = Compte.objects.get(id=request.data["source_id"])
        destination = Compte.objects.get(id=request.data["destination_id"])
        transfert = TransfertCompteService.transferer(
            source=source,
            destination=destination,
            montant=request.data["montant"],
            user=request.user,
            notes=request.data.get("notes", ""),
        )
        return Response(TransfertCompteSerializer(transfert).data, status=status.HTTP_201_CREATED)


class JournalCompteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalCompte.objects.select_related("compte")
    serializer_class = JournalCompteSerializer
    permission_classes = [permissions.IsAuthenticated]


class RapprochementBancaireViewSet(viewsets.ModelViewSet):
    queryset = RapprochementBancaire.objects.select_related("compte")
    serializer_class = RapprochementBancaireSerializer
    permission_classes = [permissions.IsAuthenticated]


class ClotureCompteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ClotureCompte.objects.select_related("compte", "cloture_par")
    serializer_class = ClotureCompteSerializer
    permission_classes = [permissions.IsAuthenticated]
