from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import (
    Compte, Devise, FinancialProvider, ModePaiement, MouvementCompte, TransfertCompte,
    JournalCompte, RapprochementBancaire, ClotureCompte,
)
from ..services import (
    MouvementCompteService, TransfertCompteService,
    ClotureCompteService, CompteService,
)
from ..selectors import ConfigurationFinanciereSelector, DashboardSelector, MouvementSelector
from ..permissions import ComptesPermission
from ..scoping import EntrepriseScopedViewSetMixin, scoping_enabled
from .serializers import (
    AjustementInputSerializer, CompteSerializer, DeviseSerializer, FinancialProviderSerializer,
    ModePaiementSerializer, MouvementCompteSerializer, MouvementInputSerializer,
    TransfertInputSerializer,
    TransfertCompteSerializer, JournalCompteSerializer,
    RapprochementBancaireSerializer, ClotureCompteSerializer,
)


class CompteViewSet(EntrepriseScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Compte.objects.all()
    serializer_class = CompteSerializer
    permission_classes = [ComptesPermission]
    permission_actions = {"recalculer_solde": "change_compte"}
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
        tenant_filter = {"entreprise_id": self.get_entreprise_id()} if scoping_enabled() else {}
        selector = DashboardSelector(tenant_filter=tenant_filter)
        return Response(selector.synthese_globale())

    @action(detail=False, methods=["get"])
    def configuration(self, request):
        entreprise_id = self.get_entreprise_id() if scoping_enabled() else ""
        selector = ConfigurationFinanciereSelector(entreprise_id=entreprise_id)
        return Response(selector.configuration())


class FinancialProviderViewSet(viewsets.ModelViewSet):
    queryset = FinancialProvider.objects.all()
    serializer_class = FinancialProviderSerializer
    permission_classes = [ComptesPermission]
    filterset_fields = ["country_code", "kind", "active", "selectable"]
    search_fields = ["code", "name", "official_name"]

    def get_queryset(self):
        qs = super().get_queryset()
        country = self.request.query_params.get("country") or self.request.query_params.get("country_code")
        kind = self.request.query_params.get("kind")
        if country:
            qs = qs.filter(country_code=country.upper())
        if kind:
            qs = qs.filter(kind=kind.upper())
        return qs


class ModePaiementViewSet(EntrepriseScopedViewSetMixin, viewsets.ModelViewSet):
    """Référentiel des seuls modes de paiement acceptés par l'organisation."""

    queryset = ModePaiement.objects.prefetch_related("comptes")
    serializer_class = ModePaiementSerializer
    permission_classes = [ComptesPermission]
    filterset_fields = ["actif", "comptes"]
    search_fields = ["code", "libelle"]


class DeviseViewSet(viewsets.ModelViewSet):
    queryset = Devise.objects.all()
    serializer_class = DeviseSerializer
    permission_classes = [ComptesPermission]
    filterset_fields = ["actif", "est_personnalisee"]
    search_fields = ["code", "nom", "symbole"]


class MouvementCompteViewSet(EntrepriseScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = MouvementCompte.objects.select_related("compte", "created_by")
    entreprise_scope_field = "entreprise_id"
    serializer_class = MouvementCompteSerializer
    permission_classes = [ComptesPermission]
    permission_actions = {
        "encaisser": "encaisser",
        "decaisser": "decaisser",
        "ajuster": "change_compte",
        "annuler": "annuler",
    }
    filterset_fields = ["compte", "nature", "statut"]
    search_fields = ["libelle", "reference"]

    @action(detail=False, methods=["post"])
    def encaisser(self, request):
        serializer = MouvementInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        compte = self._get_scoped_compte(serializer.validated_data["compte_id"])
        mvt = MouvementCompteService.encaisser(
            compte=compte,
            montant=serializer.validated_data["montant"],
            libelle=serializer.validated_data.get("libelle", ""),
            user=request.user,
            reference=serializer.validated_data.get("reference", ""),
            idempotency_key=serializer.validated_data.get("idempotency_key"),
        )
        return Response(MouvementCompteSerializer(mvt).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def decaisser(self, request):
        serializer = MouvementInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        compte = self._get_scoped_compte(serializer.validated_data["compte_id"])
        mvt = MouvementCompteService.decaisser(
            compte=compte,
            montant=serializer.validated_data["montant"],
            libelle=serializer.validated_data.get("libelle", ""),
            user=request.user,
            reference=serializer.validated_data.get("reference", ""),
            idempotency_key=serializer.validated_data.get("idempotency_key"),
        )
        return Response(MouvementCompteSerializer(mvt).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def ajuster(self, request):
        serializer = AjustementInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        compte = self._get_scoped_compte(serializer.validated_data["compte_id"])
        mvt = MouvementCompteService.ajuster(
            compte=compte,
            montant=serializer.validated_data["montant"],
            libelle=serializer.validated_data.get("libelle", ""),
            user=request.user,
            reference=serializer.validated_data.get("reference", ""),
            idempotency_key=serializer.validated_data.get("idempotency_key"),
            sens=serializer.validated_data.get("sens"),
        )
        return Response(MouvementCompteSerializer(mvt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        mvt = self.get_object()
        annulation = MouvementCompteService.annuler(
            mvt, user=request.user, raison=request.data.get("raison", "")
        )
        return Response(MouvementCompteSerializer(annulation).data)

    def _get_scoped_compte(self, compte_id):
        qs = Compte.objects.all()
        if scoping_enabled():
            qs = qs.filter(entreprise_id=self.get_entreprise_id())
        return get_object_or_404(qs, id=compte_id)


class TransfertCompteViewSet(EntrepriseScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TransfertCompte.objects.select_related("source", "destination")
    entreprise_scope_field = "entreprise_id"
    serializer_class = TransfertCompteSerializer
    permission_classes = [ComptesPermission]
    permission_actions = {"transferer": "transferer"}

    @action(detail=False, methods=["post"])
    def transferer(self, request):
        serializer = TransfertInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comptes = Compte.objects.all()
        if scoping_enabled():
            comptes = comptes.filter(entreprise_id=self.get_entreprise_id())
        source = get_object_or_404(comptes, id=serializer.validated_data["source_id"])
        destination = get_object_or_404(comptes, id=serializer.validated_data["destination_id"])
        transfert = TransfertCompteService.transferer(
            source=source,
            destination=destination,
            montant=serializer.validated_data["montant"],
            user=request.user,
            notes=serializer.validated_data.get("notes", ""),
            idempotency_key=serializer.validated_data.get("idempotency_key"),
        )
        return Response(TransfertCompteSerializer(transfert).data, status=status.HTTP_201_CREATED)


class JournalCompteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalCompte.objects.select_related("compte")
    serializer_class = JournalCompteSerializer
    permission_classes = [ComptesPermission]


class RapprochementBancaireViewSet(viewsets.ModelViewSet):
    queryset = RapprochementBancaire.objects.select_related("compte")
    serializer_class = RapprochementBancaireSerializer
    permission_classes = [ComptesPermission]
    permission_actions = {
        "create": "rapprocher", "update": "rapprocher",
        "partial_update": "rapprocher", "destroy": "rapprocher",
    }


class ClotureCompteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ClotureCompte.objects.select_related("compte", "cloture_par")
    serializer_class = ClotureCompteSerializer
    permission_classes = [ComptesPermission]
