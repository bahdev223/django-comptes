from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from comptes.api.views import MouvementCompteViewSet, TransfertCompteViewSet
from comptes.models import Compte


User = get_user_model()


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
        request = self.factory.get("/mouvements/")
        force_authenticate(request, user=self.user)
        self.assertEqual(view(request).status_code, 200)

    def test_encaissement_exige_la_permission_metier(self):
        request = self.factory.post("/mouvements/encaisser/", {}, format="json")
        force_authenticate(request, user=self.user)
        view = MouvementCompteViewSet.as_view({"post": "encaisser"})

        self.assertEqual(view(request).status_code, 403)

        self.user.user_permissions.add(Permission.objects.get(codename="encaisser"))
        compte = Compte.objects.create(code="API-001", nom="API")
        request = self.factory.post(
            "/mouvements/encaisser/",
            {"compte_id": compte.id, "montant": "100", "libelle": "Test"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        self.assertEqual(view(request).status_code, 201)
