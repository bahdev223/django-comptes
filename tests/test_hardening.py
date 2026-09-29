from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from comptes.api.views import (
    ClotureCompteViewSet,
    FinancialProviderViewSet,
    JournalCompteViewSet,
    ModePaiementViewSet,
    MouvementCompteViewSet,
    RapprochementBancaireViewSet,
)
from comptes.exceptions import IdempotencyConflict
from comptes.models import (
    ClotureCompte,
    Compte,
    FinancialProvider,
    JournalCompte,
    ProviderKind,
    RapprochementBancaire,
    TypeCompte,
)
from comptes.services import (
    ClotureCompteService,
    CompteService,
    MouvementCompteService,
    RapprochementService,
)
from comptes.seeds.providers_ml import PROVIDERS_MALI


User = get_user_model()


def tenant_resolver(request):
    return getattr(request.user, "entreprise_id", "")


TENANT_SETTINGS = {
    "SCOPING_ENABLED": True,
    "SCOPE_RESOLVER": "tests.test_hardening.tenant_resolver",
}


class TenantHardeningApiTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user("tenant-user", password="test")

    @override_settings(COMPTES=TENANT_SETTINGS)
    def test_scoping_fail_closed_sans_tenant(self):
        self.user.user_permissions.add(Permission.objects.get(codename="view_compte"))
        from comptes.api.views import CompteViewSet

        request = self.factory.get("/comptes/")
        force_authenticate(request, user=self.user)
        response = CompteViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(COMPTES=TENANT_SETTINGS)
    def test_journaux_clotures_et_rapprochements_sont_scopes(self):
        self.user.entreprise_id = "A"
        for codename in (
            "view_journalcompte",
            "view_cloturecompte",
            "view_rapprochementbancaire",
        ):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))

        compte_a = Compte.objects.create(
            entreprise_id="A", code="A-BQ", nom="Banque A", type=TypeCompte.BANQUE
        )
        compte_b = Compte.objects.create(
            entreprise_id="B", code="B-BQ", nom="Banque B", type=TypeCompte.BANQUE
        )
        JournalCompte.objects.create(compte=compte_a)
        JournalCompte.objects.create(compte=compte_b)
        ClotureCompte.objects.create(
            compte=compte_a,
            date_cloture=date.today(),
            solde_avant=0,
            solde_apres=0,
        )
        ClotureCompte.objects.create(
            compte=compte_b,
            date_cloture=date.today(),
            solde_avant=0,
            solde_apres=0,
        )
        for compte in (compte_a, compte_b):
            RapprochementBancaire.objects.create(
                compte=compte,
                date_debut=date.today(),
                date_fin=date.today(),
                date_releve=date.today(),
                solde_releve=0,
                solde_comptable=0,
            )

        for path, viewset in (
            ("/journaux/", JournalCompteViewSet),
            ("/clotures/", ClotureCompteViewSet),
            ("/rapprochements/", RapprochementBancaireViewSet),
        ):
            request = self.factory.get(path)
            force_authenticate(request, user=self.user)
            response = viewset.as_view({"get": "list"})(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), 1)

    @override_settings(COMPTES=TENANT_SETTINGS)
    def test_mode_paiement_refuse_compte_autre_tenant_des_le_serializer(self):
        self.user.entreprise_id = "A"
        self.user.user_permissions.add(Permission.objects.get(codename="add_modepaiement"))
        compte_b = Compte.objects.create(
            entreprise_id="B", code="B-CASH", nom="Caisse B"
        )
        request = self.factory.post(
            "/modes-paiement/",
            {"code": "CASH", "libelle": "Espèces", "comptes": [compte_b.pk]},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = ModePaiementViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 400)

    def test_provider_api_est_lecture_seule(self):
        self.assertFalse(hasattr(FinancialProviderViewSet, "create"))
        self.assertFalse(hasattr(FinancialProviderViewSet, "update"))
        self.assertFalse(hasattr(FinancialProviderViewSet, "destroy"))

    def test_rapprochement_api_n_expose_plus_crud_direct(self):
        self.assertFalse(hasattr(RapprochementBancaireViewSet, "create"))
        self.assertFalse(hasattr(RapprochementBancaireViewSet, "update"))
        self.assertFalse(hasattr(RapprochementBancaireViewSet, "destroy"))


class IntegrityHardeningTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cashier-hardening", password="test")
        self.user.user_permissions.add(
            Permission.objects.get(codename="encaisser"),
            Permission.objects.get(codename="change_compte"),
        )
        self.compte = Compte.objects.create(
            entreprise_id="A",
            code="CASH-A",
            nom="Caisse A",
            solde_actuel=Decimal("50000.00"),
        )

    def test_idempotency_key_refuse_payload_different(self):
        MouvementCompteService.encaisser(
            compte=self.compte,
            montant=Decimal("10000.00"),
            libelle="Vente",
            user=self.user,
            idempotency_key="sale-42",
        )
        with self.assertRaises(IdempotencyConflict):
            MouvementCompteService.encaisser(
                compte=self.compte,
                montant=Decimal("12000.00"),
                libelle="Vente",
                user=self.user,
                idempotency_key="sale-42",
            )

    def test_payload_hash_et_trace_sont_persistes(self):
        mouvement = MouvementCompteService.encaisser(
            compte=self.compte,
            montant=Decimal("1000.00"),
            libelle="Vente Fournea",
            user=self.user,
            idempotency_key="fournea-sale-1",
            source_system="fournea",
            source_type="sale",
            source_id="sale-1",
            source_reference="TICKET-001",
        )
        self.assertEqual(len(mouvement.payload_hash), 64)
        self.assertEqual(mouvement.source_system, "fournea")
        self.assertEqual(mouvement.source_type, "sale")
        self.assertEqual(mouvement.source_id, "sale-1")
        self.assertEqual(mouvement.source_reference, "TICKET-001")

    def test_un_seul_compte_par_defaut_par_entreprise(self):
        self.compte.par_defaut = True
        self.compte.save()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Compte.objects.create(
                    entreprise_id="A",
                    code="SECOND",
                    nom="Second",
                    par_defaut=True,
                )

    def test_provider_type_incompatible_refuse(self):
        provider = FinancialProvider.objects.create(
            code="ORANGE_MONEY",
            name="Orange Money",
            kind=ProviderKind.MOBILE_MONEY,
            country_code="ML",
        )
        with self.assertRaises(ValidationError):
            Compte.objects.create(
                entreprise_id="A",
                code="BAD",
                nom="Incohérent",
                provider=provider,
                type=TypeCompte.BANQUE,
            )

    def test_modification_compte_cree_un_audit(self):
        CompteService.modifier(
            self.compte,
            user=self.user,
            commentaire="Renommage test",
            nom="Nouvelle caisse",
        )
        historique = self.compte.historique.get()
        self.assertEqual(historique.ancienne_valeur, "Caisse A")
        self.assertEqual(historique.nouvelle_valeur, "Nouvelle caisse")
        self.assertEqual(historique.modifie_par, self.user)


class PermissionHardeningTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("staff-no-finance-perm", password="test")
        self.compte = Compte.objects.create(
            code="BANK-PERM", nom="Banque", type=TypeCompte.BANQUE
        )

    def test_cloture_service_exige_permission(self):
        with self.assertRaises(PermissionDenied):
            ClotureCompteService.cloturer(
                self.compte, solde_reel=Decimal("0.00"), user=self.user
            )

    def test_rapprochement_service_exige_permission(self):
        with self.assertRaises(PermissionDenied):
            RapprochementService.initialiser(
                self.compte,
                date.today(),
                date.today(),
                Decimal("0.00"),
                user=self.user,
            )


class ProviderSeedHardeningTest(TestCase):
    def test_providers_non_verifies_non_selectionnables(self):
        providers = {p["code"]: p for p in PROVIDERS_MALI}
        self.assertFalse(providers["T_LIA"]["selectable"])
        self.assertFalse(providers["OPTIMA"]["selectable"])


class PreHtmlReadinessTest(TestCase):
    def test_onboarding_cree_mode_paiement_dans_le_bon_tenant(self):
        provider = FinancialProvider.objects.create(
            code="CASH_HTML_READY",
            name="Espèces",
            kind=ProviderKind.CASH,
            country_code="ML",
        )
        from comptes.services import FinancialOnboardingService
        from comptes.models import ModePaiement

        FinancialOnboardingService.configurer_comptes(
            provider_codes=[provider.code],
            entreprise_id="TENANT-HTML",
        )

        mode = ModePaiement.objects.get(
            entreprise_id="TENANT-HTML",
            code=provider.code,
        )
        self.assertEqual(mode.entreprise_id, "TENANT-HTML")
        self.assertEqual(mode.comptes.get().entreprise_id, "TENANT-HTML")

    def test_urls_django_sont_importables_sans_wrapper_hote(self):
        import importlib
        module = importlib.import_module("comptes.urls")
        self.assertTrue(module.urlpatterns)

    @override_settings(COMPTES=TENANT_SETTINGS)
    def test_api_cloture_refuse_compte_autre_tenant(self):
        self.user = User.objects.create_user("closer", password="test")
        self.user.entreprise_id = "A"
        self.user.user_permissions.add(Permission.objects.get(codename="cloturer"))

        compte_b = Compte.objects.create(
            entreprise_id="B",
            code="B-CLOTURE",
            nom="Compte B",
            solde_actuel=Decimal("1000.00"),
        )
        factory = APIRequestFactory()
        request = factory.post(
            "/clotures/cloturer/",
            {"compte_id": compte_b.pk, "solde_reel": "1000.00"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = ClotureCompteViewSet.as_view({"post": "cloturer"})(request)
        self.assertEqual(response.status_code, 404)

    @override_settings(COMPTES=TENANT_SETTINGS)
    def test_api_cloture_compte_tenant_actif(self):
        self.user = User.objects.create_user("closer-ok", password="test")
        self.user.entreprise_id = "A"
        self.user.user_permissions.add(Permission.objects.get(codename="cloturer"))

        compte = Compte.objects.create(
            entreprise_id="A",
            code="A-CLOTURE",
            nom="Compte A",
            solde_actuel=Decimal("1000.00"),
        )
        factory = APIRequestFactory()
        request = factory.post(
            "/clotures/cloturer/",
            {"compte_id": compte.pk, "solde_reel": "1000.00"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = ClotureCompteViewSet.as_view({"post": "cloturer"})(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["compte"], compte.pk)
