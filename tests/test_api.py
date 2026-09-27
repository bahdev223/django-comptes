from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from comptes.api.views import CompteViewSet, MouvementCompteViewSet, TransfertCompteViewSet
from comptes.models import Compte


User = get_user_model()


def resolve_scope(request):
    return getattr(request.user, "entreprise_id", "")


class ApiSecurityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("api-user", password="test")
        self.factory = APIRequestFactory()

    def test_mouvements_et_transferts_ne_proposent_pas_de_crud_direct(self):
        for viewset in (MouvementCompteViewSet, TransfertCompteViewSet):
            self.assertFalse(hasattr(viewset, "create"))
            self.assertFalse(hasattr(viewset, "update"))
            self.assertFalse(hasattr(viewset, "partial_update"))
            self.assertFalse(hasattr(viewset, "destroy"))

    def test_liste_mouvements_exige_la_permission_django_standard(self):
        request = self.factory.get("/mouvements/")
        force_authenticate(request, user=self.user)
        view = MouvementCompteViewSet.as_view({"get": "list"})

        self.assertEqual(view(request).status_code, 403)

        self.user.user_permissions.add(
            Permission.objects.get(codename="view_mouvementcompte")
        )
        self.user = User.objects.get(pk=self.user.pk)
        request = self.factory.get("/mouvements/")
        force_authenticate(request, user=self.user)
        self.assertEqual(view(request).status_code, 200)

    def test_encaissement_exige_la_permission_metier(self):
        request = self.factory.post("/mouvements/encaisser/", {}, format="json")
        force_authenticate(request, user=self.user)
        view = MouvementCompteViewSet.as_view({"post": "encaisser"})

        self.assertEqual(view(request).status_code, 403)

        self.user.user_permissions.add(Permission.objects.get(codename="encaisser"))
        self.user = User.objects.get(pk=self.user.pk)
        compte = Compte.objects.create(code="API-001", nom="API")
        request = self.factory.post(
            "/mouvements/encaisser/",
            {"compte_id": compte.id, "montant": "100", "libelle": "Test"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        self.assertEqual(view(request).status_code, 201)

    @override_settings(
        COMPTES={"SCOPING_ENABLED": True, "SCOPE_RESOLVER": "tests.test_api.resolve_scope"}
    )
    def test_liste_comptes_est_scopee_par_entreprise(self):
        self.user.entreprise_id = "A"
        self.user.user_permissions.add(Permission.objects.get(codename="view_compte"))
        Compte.objects.create(entreprise_id="A", code="A-001", nom="Compte A")
        Compte.objects.create(entreprise_id="B", code="B-001", nom="Compte B")

        request = self.factory.get("/comptes/")
        force_authenticate(request, user=self.user)
        view = CompteViewSet.as_view({"get": "list"})

        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["code"], "A-001")

    @override_settings(
        COMPTES={"SCOPING_ENABLED": True, "SCOPE_RESOLVER": "tests.test_api.resolve_scope"}
    )
    def test_encaissement_refuse_un_compte_autre_entreprise(self):
        self.user.entreprise_id = "A"
        self.user.user_permissions.add(Permission.objects.get(codename="encaisser"))
        compte_b = Compte.objects.create(entreprise_id="B", code="B-001", nom="Compte B")
        request = self.factory.post(
            "/mouvements/encaisser/",
            {"compte_id": compte_b.id, "montant": "100", "libelle": "Cross tenant"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        view = MouvementCompteViewSet.as_view({"post": "encaisser"})

        self.assertEqual(view(request).status_code, 404)
