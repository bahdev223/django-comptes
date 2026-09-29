from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..exceptions import IdempotencyConflict
from ..models import (
    ClotureCompte,
    Compte,
    Devise,
    FinancialProvider,
    JournalCompte,
    ModePaiement,
    MouvementCompte,
    RapprochementBancaire,
    TransfertCompte,
)
from ..permissions import ComptesPermission
from ..scoping import EntrepriseScopedViewSetMixin, scoping_enabled
from ..selectors import ConfigurationFinanciereSelector, DashboardSelector
from ..services import (
    ClotureCompteService,
    CompteService,
    MouvementCompteService,
    RapprochementService,
    TransfertCompteService,
)
from .serializers import (
    AjustementInputSerializer,
    ClotureCompteSerializer,
    ClotureInputSerializer,
    CompteSerializer,
    DeviseSerializer,
    FinancialProviderSerializer,
    JournalCompteSerializer,
    LigneReleveInputSerializer,
    ModePaiementSerializer,
    MouvementCompteSerializer,
    MouvementInputSerializer,
    RapprochementBancaireSerializer,
    RapprochementInitialiserSerializer,
    RapprochementLigneSerializer,
    TransfertCompteSerializer,
    TransfertInputSerializer,
)


def _idempotency_conflict_response(exc):
    return Response(
        {"detail": str(exc), "code": "idempotency_conflict"},
        status=status.HTTP_409_CONFLICT,
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
        return Response([
            {
                "date": x.created_at.isoformat(),
                "type": x.type_changement,
                "ancien": x.ancienne_valeur,
                "nouveau": x.nouvelle_valeur,
                "commentaire": x.commentaire,
            }
            for x in h
        ])

    @action(detail=False, methods=["get"])
    def synthese(self, request):
        tenant_filter = (
            {"entreprise_id": self.get_entreprise_id()} if scoping_enabled() else {}
        )
        return Response(DashboardSelector(tenant_filter=tenant_filter).synthese_globale())

    @action(detail=False, methods=["get"])
    def configuration(self, request):
        entreprise_id = self.get_entreprise_id() if scoping_enabled() else ""
        return Response(
            ConfigurationFinanciereSelector(entreprise_id=entreprise_id).configuration()
        )


class FinancialProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """Référentiel global en lecture seule via API.

    Les mutations passent par les seeds/services d'administration de la plateforme.
    """

    queryset = FinancialProvider.objects.all()
    serializer_class = FinancialProviderSerializer
    permission_classes = [ComptesPermission]
    filterset_fields = ["country_code", "kind", "active", "selectable"]
    search_fields = ["code", "name", "official_name"]

    def get_queryset(self):
        qs = super().get_queryset()
        country = (
            self.request.query_params.get("country")
            or self.request.query_params.get("country_code")
        )
        kind = self.request.query_params.get("kind")
        if country:
            qs = qs.filter(country_code=country.upper())
        if kind:
            qs = qs.filter(kind=kind.upper())
        return qs


class ModePaiementViewSet(EntrepriseScopedViewSetMixin, viewsets.ModelViewSet):
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
    search_fields = ["libelle", "reference", "source_reference"]

    def _trace_kwargs(self, data):
        return {
            "source_system": data.get("source_system", ""),
            "source_type": data.get("source_type", ""),
            "source_id": data.get("source_id", ""),
            "source_reference": data.get("source_reference", ""),
        }

    @action(detail=False, methods=["post"])
    def encaisser(self, request):
        serializer = MouvementInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        compte = self._get_scoped_compte(data["compte_id"])
        try:
            mvt = MouvementCompteService.encaisser(
                compte=compte,
                montant=data["montant"],
                libelle=data.get("libelle", ""),
                user=request.user,
                reference=data.get("reference", ""),
                idempotency_key=data.get("idempotency_key"),
                **self._trace_kwargs(data),
            )
        except IdempotencyConflict as exc:
            return _idempotency_conflict_response(exc)
        return Response(MouvementCompteSerializer(mvt).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def decaisser(self, request):
        serializer = MouvementInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        compte = self._get_scoped_compte(data["compte_id"])
        try:
            mvt = MouvementCompteService.decaisser(
                compte=compte,
                montant=data["montant"],
                libelle=data.get("libelle", ""),
                user=request.user,
                reference=data.get("reference", ""),
                idempotency_key=data.get("idempotency_key"),
                **self._trace_kwargs(data),
            )
        except IdempotencyConflict as exc:
            return _idempotency_conflict_response(exc)
        return Response(MouvementCompteSerializer(mvt).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def ajuster(self, request):
        serializer = AjustementInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        compte = self._get_scoped_compte(data["compte_id"])
        try:
            mvt = MouvementCompteService.ajuster(
                compte=compte,
                montant=data["montant"],
                libelle=data.get("libelle", ""),
                user=request.user,
                reference=data.get("reference", ""),
                idempotency_key=data.get("idempotency_key"),
                sens=data.get("sens"),
                **self._trace_kwargs(data),
            )
        except IdempotencyConflict as exc:
            return _idempotency_conflict_response(exc)
        return Response(MouvementCompteSerializer(mvt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        annulation = MouvementCompteService.annuler(
            self.get_object(),
            user=request.user,
            raison=request.data.get("raison", ""),
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
        data = serializer.validated_data
        comptes = Compte.objects.all()
        if scoping_enabled():
            comptes = comptes.filter(entreprise_id=self.get_entreprise_id())
        source = get_object_or_404(comptes, id=data["source_id"])
        destination = get_object_or_404(comptes, id=data["destination_id"])
        try:
            transfert = TransfertCompteService.transferer(
                source=source,
                destination=destination,
                montant=data["montant"],
                user=request.user,
                notes=data.get("notes", ""),
                idempotency_key=data.get("idempotency_key"),
                source_system=data.get("source_system", ""),
                source_type=data.get("source_type", ""),
                external_source_id=data.get("external_source_id", ""),
                source_reference=data.get("source_reference", ""),
            )
        except IdempotencyConflict as exc:
            return _idempotency_conflict_response(exc)
        return Response(
            TransfertCompteSerializer(transfert).data,
            status=status.HTTP_201_CREATED,
        )


class JournalCompteViewSet(EntrepriseScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = JournalCompte.objects.select_related("compte")
    entreprise_scope_field = "compte__entreprise_id"
    serializer_class = JournalCompteSerializer
    permission_classes = [ComptesPermission]


class RapprochementBancaireViewSet(
    EntrepriseScopedViewSetMixin, viewsets.ReadOnlyModelViewSet
):
    queryset = RapprochementBancaire.objects.select_related("compte")
    entreprise_scope_field = "compte__entreprise_id"
    serializer_class = RapprochementBancaireSerializer
    permission_classes = [ComptesPermission]
    permission_actions = {
        "initialiser": "rapprocher",
        "pointer": "rapprocher",
        "depointer": "rapprocher",
        "ajouter_ligne_releve": "rapprocher",
        "valider": "rapprocher",
    }

    @action(detail=False, methods=["post"])
    def initialiser(self, request):
        serializer = RapprochementInitialiserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        comptes = Compte.objects.all()
        if scoping_enabled():
            comptes = comptes.filter(entreprise_id=self.get_entreprise_id())
        compte = get_object_or_404(comptes, pk=data["compte_id"])
        rapprochement = RapprochementService.initialiser(
            compte=compte,
            date_debut=data["date_debut"],
            date_fin=data["date_fin"],
            solde_releve=data["solde_releve"],
            date_releve=data.get("date_releve"),
            user=request.user,
        )
        return Response(
            RapprochementBancaireSerializer(rapprochement).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def pointer(self, request, pk=None):
        serializer = RapprochementLigneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rapprochement = RapprochementService.pointer(
            self.get_object(), serializer.validated_data["ligne_id"], user=request.user
        )
        return Response(RapprochementBancaireSerializer(rapprochement).data)

    @action(detail=True, methods=["post"])
    def depointer(self, request, pk=None):
        serializer = RapprochementLigneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rapprochement = RapprochementService.depointer(
            self.get_object(), serializer.validated_data["ligne_id"], user=request.user
        )
        return Response(RapprochementBancaireSerializer(rapprochement).data)

    @action(detail=True, methods=["post"], url_path="ajouter-ligne-releve")
    def ajouter_ligne_releve(self, request, pk=None):
        serializer = LigneReleveInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ligne = RapprochementService.ajouter_ligne_releve(
            self.get_object(),
            user=request.user,
            **serializer.validated_data,
        )
        return Response({"id": ligne.pk}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        rapprochement = RapprochementService.valider(
            self.get_object(), user=request.user
        )
        return Response(RapprochementBancaireSerializer(rapprochement).data)


class ClotureCompteViewSet(EntrepriseScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ClotureCompte.objects.select_related("compte", "cloture_par")
    entreprise_scope_field = "compte__entreprise_id"
    serializer_class = ClotureCompteSerializer
    permission_classes = [ComptesPermission]
    permission_actions = {"cloturer": "cloturer"}

    @action(detail=False, methods=["post"])
    def cloturer(self, request):
        serializer = ClotureInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        comptes = Compte.objects.filter(actif=True)
        if scoping_enabled():
            comptes = comptes.filter(entreprise_id=self.get_entreprise_id())
        compte = get_object_or_404(comptes, pk=data["compte_id"])

        cloture = ClotureCompteService.cloturer(
            compte=compte,
            solde_reel=data.get("solde_reel"),
            user=request.user,
            commentaire=data.get("commentaire", ""),
            date_cloture=data.get("date_cloture"),
        )
        return Response(
            ClotureCompteSerializer(cloture).data,
            status=status.HTTP_201_CREATED,
        )
