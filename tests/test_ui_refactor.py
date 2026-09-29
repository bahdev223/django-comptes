from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase, override_settings

from comptes.admin import MouvementCompteAdmin, TransfertCompteAdmin
from comptes.models import FinancialProvider, MouvementCompte, ProviderKind, TransfertCompte
from comptes.views.onboarding import onboarding_financier


User = get_user_model()


def resolve_ui_scope(request):
    return getattr(request.user, "entreprise_id", "")


UI_SCOPE = {
    "SCOPING_ENABLED": True,
    "SCOPE_RESOLVER": "tests.test_ui_refactor.resolve_ui_scope",
}


class UiRefactorTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(
            username="ui-admin",
            email="ui@example.com",
            password="test",
        )
        self.user.entreprise_id = "TENANT-UI"

    def request(self, method="get", data=None):
        request = getattr(self.factory, method)("/finance/onboarding/", data=data or {})
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    @override_settings(COMPTES=UI_SCOPE)
    def test_onboarding_html_configure_le_tenant_actif(self):
        FinancialProvider.objects.create(
            code="UI_CASH",
            name="Espèces UI",
            kind=ProviderKind.CASH,
            country_code="ML",
            active=True,
            selectable=True,
        )
        request = self.request("post", {"providers": ["UI_CASH"]})
        response = onboarding_financier(request)

        self.assertEqual(response.status_code, 302)
        from comptes.models import Compte, ModePaiement
        self.assertTrue(
            Compte.objects.filter(
                entreprise_id="TENANT-UI",
                provider__code="UI_CASH",
            ).exists()
        )
        self.assertTrue(
            ModePaiement.objects.filter(
                entreprise_id="TENANT-UI",
                code="UI_CASH",
            ).exists()
        )

    def test_admin_mouvements_et_transferts_restent_read_only(self):
        mouvement_admin = MouvementCompteAdmin(MouvementCompte, admin.site)
        transfert_admin = TransfertCompteAdmin(TransfertCompte, admin.site)
        request = self.request()

        self.assertFalse(mouvement_admin.has_add_permission(request))
        self.assertFalse(mouvement_admin.has_delete_permission(request))
        self.assertFalse(transfert_admin.has_add_permission(request))
        self.assertFalse(transfert_admin.has_delete_permission(request))

    def test_admin_charge_la_feuille_de_style_finance(self):
        mouvement_admin = MouvementCompteAdmin(MouvementCompte, admin.site)
        self.assertIn("comptes/admin.css", mouvement_admin.media._css["all"])
