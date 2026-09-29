from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from comptes.models import (
    Compte,
    MouvementCompte,
    NatureMouvement,
    RapprochementBancaire,
    TypeCompte,
)
from comptes.views import comptes as comptes_views
from comptes.views import dashboard as dashboard_view
from comptes.views import journal as journal_views
from comptes.views import mouvements as mouvement_views
from comptes.views import rapprochement as rapprochement_views
from comptes.views import transferts as transfert_views


User = get_user_model()


def resolve_html_scope(request):
    return getattr(request.user, "entreprise_id", "")


HTML_TENANT_SETTINGS = {
    "SCOPING_ENABLED": True,
    "SCOPE_RESOLVER": "tests.test_html_security.resolve_html_scope",
}


class HtmlTenantSecurityTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(
            username="html-admin",
            email="html@example.com",
            password="test",
        )
        self.user.entreprise_id = "A"
        self.compte_a = Compte.objects.create(
            entreprise_id="A",
            code="A-CASH",
            nom="Caisse A",
            solde_actuel=Decimal("10000.00"),
        )
        self.compte_b = Compte.objects.create(
            entreprise_id="B",
            code="B-CASH",
            nom="Caisse B",
            solde_actuel=Decimal("20000.00"),
        )

    def request(self, method="get", path="/", data=None):
        maker = getattr(self.factory, method)
        request = maker(path, data=data or {})
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    @override_settings(COMPTES=HTML_TENANT_SETTINGS)
    def test_liste_comptes_ne_contient_que_tenant_actif(self):
        request = self.request()
        with patch("comptes.views.comptes.render") as mocked:
            mocked.return_value.status_code = 200
            comptes_views.liste_comptes(request)
        context = mocked.call_args.args[2]
        self.assertEqual(list(context["comptes"]), [self.compte_a])
        self.assertEqual(context["synthese"]["nb_comptes_actifs"], 1)

    @override_settings(COMPTES=HTML_TENANT_SETTINGS)
    def test_detail_compte_autre_tenant_retourne_404(self):
        request = self.request()
        with self.assertRaises(Http404):
            comptes_views.detail_compte(request, self.compte_b.pk)

    @override_settings(COMPTES=HTML_TENANT_SETTINGS)
    def test_creation_compte_injecte_entreprise_active(self):
        request = self.request(
            "post",
            "/comptes/ajouter/",
            {
                "code": "NEW-A",
                "nom": "Nouveau A",
                "type": "ESPECES",
                "solde_initial": "0",
                "actif": "on",
                "devise": "XOF",
            },
        )
        response = comptes_views.ajouter_compte(request)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Compte.objects.filter(
                entreprise_id="A",
                code="NEW-A",
            ).exists()
        )

    @override_settings(COMPTES=HTML_TENANT_SETTINGS)
    def test_liste_mouvements_ne_fuit_pas_autre_tenant(self):
        MouvementCompte.objects.create(
            compte=self.compte_a,
            entreprise_id="A",
            nature=NatureMouvement.ENCAISSEMENT,
            montant=Decimal("100.00"),
            libelle="A",
        )
        MouvementCompte.objects.create(
            compte=self.compte_b,
            entreprise_id="B",
            nature=NatureMouvement.ENCAISSEMENT,
            montant=Decimal("200.00"),
            libelle="B",
        )
        request = self.request()
        with patch("comptes.views.mouvements.render") as mocked:
            mocked.return_value.status_code = 200
            mouvement_views.liste_mouvements(request)
        context = mocked.call_args.args[2]
        self.assertEqual([m.libelle for m in context["mouvements"]], ["A"])
        self.assertEqual(list(context["comptes"]), [self.compte_a])

    @override_settings(COMPTES=HTML_TENANT_SETTINGS)
    def test_encaissement_html_ne_peut_pas_cibler_compte_autre_tenant(self):
        request = self.request(
            "post",
            "/mouvements/encaisser/",
            {"compte_id": self.compte_b.pk, "montant": "1000"},
        )
        response = mouvement_views.mouvement_encaisser(request)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            MouvementCompte.objects.filter(
                compte=self.compte_b,
                source_system="django-html",
            ).exists()
        )

    @override_settings(COMPTES=HTML_TENANT_SETTINGS)
    def test_transfert_html_inter_tenant_est_impossible(self):
        request = self.request(
            "post",
            "/transferts/",
            {
                "source_id": self.compte_a.pk,
                "dest_id": self.compte_b.pk,
                "montant": "1000",
            },
        )
        response = transfert_views.transfert_effectuer(request)
        self.assertEqual(response.status_code, 200)
        self.compte_a.refresh_from_db()
        self.compte_b.refresh_from_db()
        self.assertEqual(self.compte_a.solde_actuel, Decimal("10000.00"))
        self.assertEqual(self.compte_b.solde_actuel, Decimal("20000.00"))

    @override_settings(COMPTES=HTML_TENANT_SETTINGS)
    def test_journal_autre_tenant_retourne_404(self):
        request = self.request()
        with self.assertRaises(Http404):
            journal_views.journal_consulter(request, compte_id=self.compte_b.pk)

    @override_settings(COMPTES=HTML_TENANT_SETTINGS)
    def test_rapprochement_detail_autre_tenant_retourne_404(self):
        banque_b = Compte.objects.create(
            entreprise_id="B",
            code="B-BANK",
            nom="Banque B",
            type=TypeCompte.BANQUE,
        )
        rapprochement = RapprochementBancaire.objects.create(
            compte=banque_b,
            date_debut="2026-09-01",
            date_fin="2026-09-29",
            date_releve="2026-09-29",
            solde_releve=Decimal("0.00"),
            solde_comptable=Decimal("0.00"),
        )
        request = self.request()
        with self.assertRaises(Http404):
            rapprochement_views.rapprochement_detail(
                request, rapprochement.pk
            )

    @override_settings(COMPTES=HTML_TENANT_SETTINGS)
    def test_dashboard_est_scope(self):
        request = self.request()
        with patch("comptes.views.dashboard.render") as mocked:
            mocked.return_value.status_code = 200
            dashboard_view(request)
        context = mocked.call_args.args[2]
        self.assertEqual(list(context["comptes"]), [self.compte_a])
        self.assertEqual(context["synthese"]["nb_comptes_actifs"], 1)
