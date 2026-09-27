"""
Tests des services metier du module comptes.
"""

from decimal import Decimal
from datetime import date
from pathlib import Path
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from comptes.models import (
    Compte, Devise, FinancialProvider, ProviderKind, TypeCompte, MouvementCompte,
    NatureMouvement, SensMouvement, StatutMouvement, TransfertCompte,
    JournalCompte, ClotureCompte, ModePaiement,
)
from comptes.selectors import ConfigurationFinanciereSelector, DashboardSelector
from comptes.services import (
    CompteService, MouvementCompteService,
    TransfertCompteService, ClotureCompteService,
    JournalCompteService, RapprochementService, FinancialOnboardingService,
)
from comptes.seeds.providers_ml import PROVIDERS_MALI

User = get_user_model()


class CompteServiceTest(TestCase):
    def test_creer_compte(self):
        compte = CompteService.creer(
            code="SRV-001",
            nom="Service Compte",
            type_compte=TypeCompte.ESPECES,
            solde_initial=Decimal("75000.00"),
            devise="XOF",
            compte_comptable_code="5711",
        )
        self.assertEqual(compte.solde_actuel, Decimal("75000.00"))
        self.assertEqual(compte.compte_comptable_code, "5711")

    def test_recalculer_solde(self):
        compte = Compte.objects.create(
            code="REC-001", nom="Recalcul",
            solde_actuel=Decimal("10000.00"),
        )
        MouvementCompte.objects.create(
            compte=compte,
            nature=NatureMouvement.ENCAISSEMENT,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("5000.00"),
            libelle="Test",
        )
        MouvementCompte.objects.create(
            compte=compte,
            nature=NatureMouvement.DECAISSEMENT,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("2000.00"),
            libelle="Test sortie",
        )
        nouveau_solde = CompteService.recalculer_solde(compte)
        self.assertEqual(nouveau_solde, Decimal("13000.00"))
        compte.refresh_from_db()
        self.assertEqual(compte.solde_actuel, Decimal("13000.00"))
        self.assertIsNotNone(compte.dernier_recalcul)

    def test_modifier_refuse_les_champs_financiers_et_tenant(self):
        compte = Compte.objects.create(
            entreprise_id="A",
            code="LOCK-001",
            nom="Compte verrouillé",
            solde_actuel=Decimal("10000.00"),
        )

        CompteService.modifier(
            compte,
            nom="Compte renommé",
            solde_actuel=Decimal("999999.00"),
            entreprise_id="B",
        )

        compte.refresh_from_db()
        self.assertEqual(compte.nom, "Compte renommé")
        self.assertEqual(compte.solde_actuel, Decimal("10000.00"))
        self.assertEqual(compte.entreprise_id, "A")


class FinancialProviderSeedTest(TestCase):
    def test_seed_mali_contient_les_providers_reglementaires(self):
        codes = {provider["code"] for provider in PROVIDERS_MALI}

        self.assertEqual(
            codes,
            {
                "CASH",
                "BDM",
                "BIM",
                "BNDA",
                "BCS",
                "BOA_MALI",
                "AFG_MALI",
                "BANQUE_ATLANTIQUE_MALI",
                "BMS",
                "BCI_MALI",
                "BSIC_MALI",
                "ECOBANK_MALI",
                "CORIS_MALI",
                "UBA_MALI",
                "ORABANK_MALI",
                "ORANGE_MONEY",
                "MOOV_MONEY",
                "WIZALL",
                "ZELIA",
                "CORIS_MONEY",
                "SAMA_MONEY",
                "WAVE",
                "T_LIA",
                "OPTIMA",
                "INTOUCH_MALI",
                "CAURIDOR",
            },
        )

        banks = [p for p in PROVIDERS_MALI if p["kind"] == ProviderKind.BANK]
        mobile_money = [p for p in PROVIDERS_MALI if p["kind"] == ProviderKind.MOBILE_MONEY]
        payment_institutions = [
            p for p in PROVIDERS_MALI if p["kind"] == ProviderKind.PAYMENT_INSTITUTION
        ]

        self.assertEqual(len(banks), 14)
        self.assertEqual(len(mobile_money), 9)
        self.assertEqual(len(payment_institutions), 2)
        self.assertEqual(
            next(p for p in PROVIDERS_MALI if p["code"] == "AFG_MALI")["logo"],
            "providers/ml/banks/afg-bank.svg",
        )
        self.assertEqual(
            next(p for p in PROVIDERS_MALI if p["code"] == "BCI_MALI")["logo"],
            "providers/ml/banks/bci.svg",
        )
        self.assertFalse(
            next(p for p in PROVIDERS_MALI if p["code"] == "INTOUCH_MALI")["selectable"]
        )

    def test_seed_mali_pointe_vers_des_logos_packages(self):
        package_root = Path(__file__).resolve().parents[1] / "comptes" / "assets"
        providers_with_logo = [provider for provider in PROVIDERS_MALI if provider.get("logo")]

        self.assertTrue(providers_with_logo)
        for provider in providers_with_logo:
            logo_path = package_root / provider["logo"]

            self.assertTrue(logo_path.exists(), f"{provider['code']} logo absent: {logo_path}")
            self.assertGreater(logo_path.stat().st_size, 300, f"{provider['code']} logo vide")
            self.assertIn("<svg", logo_path.read_text(encoding="utf-8", errors="ignore")[:200])


class FinancialOnboardingServiceTest(TestCase):
    def setUp(self):
        for data in [
            {
                "code": "CASH",
                "name": "Espèces",
                "kind": ProviderKind.CASH,
                "country_code": "ML",
            },
            {
                "code": "ORANGE_MONEY",
                "name": "Orange Money",
                "kind": ProviderKind.MOBILE_MONEY,
                "country_code": "ML",
            },
            {
                "code": "WAVE",
                "name": "Wave",
                "kind": ProviderKind.MOBILE_MONEY,
                "country_code": "ML",
            },
            {
                "code": "ECOBANK_MALI",
                "name": "Ecobank",
                "kind": ProviderKind.BANK,
                "country_code": "ML",
            },
        ]:
            FinancialProvider.objects.create(**data)

    def test_cree_uniquement_les_comptes_choisis(self):
        comptes = FinancialOnboardingService.configurer_comptes(
            provider_codes=["CASH"],
            entreprise_id="boutique-1",
        )

        self.assertEqual([compte.nom for compte in comptes], ["Caisse"])
        self.assertEqual(
            list(Compte.objects.filter(entreprise_id="boutique-1").values_list("provider__code", flat=True)),
            ["CASH"],
        )
        self.assertFalse(Compte.objects.filter(provider__kind=ProviderKind.BANK).exists())
        self.assertFalse(Compte.objects.filter(provider__kind=ProviderKind.MOBILE_MONEY).exists())

    def test_lie_les_modes_de_paiement_aux_comptes_acceptant_les_ventes(self):
        FinancialOnboardingService.configurer_comptes(
            provider_codes=["CASH", "ORANGE_MONEY", "WAVE"],
            entreprise_id="boutique-2",
        )

        self.assertEqual(
            list(
                Compte.objects.filter(entreprise_id="boutique-2")
                .order_by("code")
                .values_list("provider__code", flat=True)
            ),
            ["CASH", "ORANGE_MONEY", "WAVE"],
        )
        self.assertFalse(Compte.objects.filter(provider__code="ECOBANK_MALI").exists())
        self.assertEqual(
            set(ModePaiement.objects.values_list("code", flat=True)),
            {"CASH", "ORANGE_MONEY", "WAVE"},
        )

    def test_peut_creer_un_compte_personnalise_sans_provider(self):
        comptes = FinancialOnboardingService.configurer_comptes(
            provider_codes=[],
            comptes_personnalises=[
                {
                    "nom": "Autre service Mobile Money",
                    "type_compte": TypeCompte.MOBILE_MONEY,
                    "identifiant": "Service local",
                }
            ],
            entreprise_id="boutique-3",
        )

        self.assertEqual(len(comptes), 1)
        self.assertIsNone(comptes[0].provider)
        self.assertEqual(comptes[0].nom, "Autre service Mobile Money")
        self.assertEqual(comptes[0].identifiant, "Service local")


class MouvementCompteServiceTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="MVT-001", nom="Test Mouvements",
            solde_actuel=Decimal("50000.00"),
        )
        self.user = User.objects.create_user("caissier", password="test", is_staff=True)
        self.user.user_permissions.add(
            Permission.objects.get(codename="encaisser"),
            Permission.objects.get(codename="decaisser"),
            Permission.objects.get(codename="change_compte"),
            Permission.objects.get(codename="annuler"),
        )

    def test_encaisser(self):
        mvt = MouvementCompteService.encaisser(
            compte=self.compte,
            montant=Decimal("10000.00"),
            libelle="Depot test",
            user=self.user,
            reference="REF-001",
        )
        self.assertEqual(mvt.nature, NatureMouvement.ENCAISSEMENT)
        self.assertEqual(mvt.statut, StatutMouvement.VALIDE)
        self.assertEqual(mvt.montant, Decimal("10000.00"))
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_actuel, Decimal("60000.00"))

    def test_decaisser_solde_suffisant(self):
        mvt = MouvementCompteService.decaisser(
            compte=self.compte,
            montant=Decimal("30000.00"),
            libelle="Retrait test",
            user=self.user,
        )
        self.assertEqual(mvt.nature, NatureMouvement.DECAISSEMENT)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_actuel, Decimal("20000.00"))

    def test_decaisser_solde_insuffisant(self):
        with self.assertRaises(ValueError):
            MouvementCompteService.decaisser(
                compte=self.compte,
                montant=Decimal("100000.00"),
                libelle="Retrait impossible",
                user=self.user,
            )

    @override_settings(COMPTES={"ALLOW_OVERDRAFT": True})
    def test_decaisser_avec_decouvert(self):
        self.compte.autoriser_decouvert = True
        self.compte.limite_decouvert = Decimal("50000.00")
        self.compte.save()
        mvt = MouvementCompteService.decaisser(
            compte=self.compte,
            montant=Decimal("80000.00"),
            libelle="Retrait avec decouvert",
            user=self.user,
        )
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_actuel, Decimal("-30000.00"))
        self.assertTrue(self.compte.est_a_decouvert)

    def test_annuler_mouvement(self):
        mvt = MouvementCompteService.encaisser(
            compte=self.compte, montant=Decimal("5000.00"),
            libelle="Test annulation", user=self.user,
        )
        annulation = MouvementCompteService.annuler(
            mvt, user=self.user, raison="Erreur de saisie"
        )
        self.assertEqual(annulation.nature, NatureMouvement.ANNULATION)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_actuel, Decimal("50000.00"))
        mvt.refresh_from_db()
        self.assertTrue(mvt.annule)

    def test_encaissement_idempotent(self):
        premier = MouvementCompteService.encaisser(
            compte=self.compte,
            montant=Decimal("10000.00"),
            libelle="Paiement API",
            user=self.user,
            idempotency_key="payment-123",
        )
        second = MouvementCompteService.encaisser(
            compte=self.compte,
            montant=Decimal("10000.00"),
            libelle="Paiement API",
            user=self.user,
            idempotency_key="payment-123",
        )

        self.assertEqual(premier.pk, second.pk)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_actuel, Decimal("60000.00"))

    def test_meme_cle_idempotence_autorisee_sur_deux_entreprises(self):
        compte_b = Compte.objects.create(
            entreprise_id="B",
            code="MVT-001",
            nom="Compte B",
            solde_actuel=Decimal("50000.00"),
        )

        mvt_a = MouvementCompteService.encaisser(
            compte=self.compte,
            montant=Decimal("10000.00"),
            libelle="Paiement A",
            user=self.user,
            idempotency_key="payment-123",
        )
        mvt_b = MouvementCompteService.encaisser(
            compte=compte_b,
            montant=Decimal("15000.00"),
            libelle="Paiement B",
            user=self.user,
            idempotency_key="payment-123",
        )

        self.assertNotEqual(mvt_a.pk, mvt_b.pk)
        self.assertEqual(mvt_a.entreprise_id, self.compte.entreprise_id)
        self.assertEqual(mvt_b.entreprise_id, "B")

    def test_mouvement_valide_immutable(self):
        mouvement = MouvementCompteService.encaisser(
            compte=self.compte,
            montant=Decimal("10000.00"),
            libelle="Paiement API",
            user=self.user,
        )
        mouvement.montant = Decimal("1.00")

        with self.assertRaisesRegex(ValueError, "ne peut pas être modifié"):
            mouvement.save()


class TransfertCompteServiceTest(TestCase):
    def setUp(self):
        self.source = Compte.objects.create(
            code="SRC-SRV", nom="Source",
            solde_actuel=Decimal("100000.00"),
        )
        self.dest = Compte.objects.create(
            code="DST-SRV", nom="Destination",
            solde_actuel=Decimal("0.00"),
        )
        self.user = User.objects.create_user("gerant", password="test", is_staff=True)
        self.user.user_permissions.add(Permission.objects.get(codename="transferer"))

    def test_transfert_reussi(self):
        t = TransfertCompteService.transferer(
            source=self.source, destination=self.dest,
            montant=Decimal("40000.00"), user=self.user,
            notes="Virement test",
        )
        self.source.refresh_from_db()
        self.dest.refresh_from_db()
        self.assertEqual(self.source.solde_actuel, Decimal("60000.00"))
        self.assertEqual(self.dest.solde_actuel, Decimal("40000.00"))
        self.assertIsNotNone(t)

    def test_transfert_meme_compte(self):
        with self.assertRaises(ValueError):
            TransfertCompteService.transferer(
                source=self.source, destination=self.source,
                montant=Decimal("1000.00"), user=self.user,
            )

    def test_transfert_solde_insuffisant(self):
        with self.assertRaises(ValueError):
            TransfertCompteService.transferer(
                source=self.source, destination=self.dest,
                montant=Decimal("999999.00"), user=self.user,
            )

    def test_transfert_inter_entreprises_refuse(self):
        autre = Compte.objects.create(
            entreprise_id="AUTRE",
            code="DST-SRV",
            nom="Destination autre entreprise",
            solde_actuel=Decimal("0.00"),
        )

        with self.assertRaisesRegex(ValueError, "même entreprise"):
            TransfertCompteService.transferer(
                source=self.source,
                destination=autre,
                montant=Decimal("1000.00"),
                user=self.user,
            )

    def test_transfert_idempotent(self):
        premier = TransfertCompteService.transferer(
            source=self.source,
            destination=self.dest,
            montant=Decimal("40000.00"),
            user=self.user,
            idempotency_key="transfer-123",
        )
        second = TransfertCompteService.transferer(
            source=self.source,
            destination=self.dest,
            montant=Decimal("40000.00"),
            user=self.user,
            idempotency_key="transfer-123",
        )

        self.assertEqual(premier.pk, second.pk)
        self.source.refresh_from_db()
        self.dest.refresh_from_db()
        self.assertEqual(self.source.solde_actuel, Decimal("60000.00"))
        self.assertEqual(self.dest.solde_actuel, Decimal("40000.00"))


class ClotureCompteServiceTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="CLT-SRV", nom="Test Cloture",
            solde_actuel=Decimal("75000.00"),
        )

    def test_cloture_journaliere(self):
        cloture = ClotureCompteService.cloturer(
            compte=self.compte,
            solde_reel=Decimal("75000.00"),
        )
        self.assertIsNotNone(cloture)
        self.assertEqual(cloture.solde_avant, cloture.solde_apres)

    def test_cloture_avec_ecart(self):
        cloture = ClotureCompteService.cloturer(
            compte=self.compte,
            solde_reel=Decimal("74000.00"),
            commentaire="Ecart de -1000",
        )
        self.assertEqual(cloture.ecart, Decimal("-1000.00"))


class JournalCompteServiceTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="JRN-SRV", nom="Test Journal",
            solde_actuel=Decimal("50000.00"),
        )

    def test_obtenir_ou_creer(self):
        journal = JournalCompteService.obtenir_ou_creer(self.compte)
        self.assertIsNotNone(journal)
        self.assertEqual(journal.compte, self.compte)

    def test_calculer_totaux(self):
        aujourdhui = date.today()
        MouvementCompte.objects.create(
            compte=self.compte,
            nature=NatureMouvement.ENCAISSEMENT,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("10000.00"),
            libelle="Test",
        )
        MouvementCompte.objects.create(
            compte=self.compte,
            nature=NatureMouvement.DECAISSEMENT,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("3000.00"),
            libelle="Test sortie",
        )
        entrees, sorties = JournalCompteService.calculer_totaux(
            self.compte, aujourdhui
        )
        self.assertEqual(entrees, Decimal("10000.00"))
        self.assertEqual(sorties, Decimal("3000.00"))


class RapprochementServiceTest(TestCase):
    def test_solde_comptable_utilise_le_sens_des_mouvements(self):
        compte = Compte.objects.create(code="RAPP-001", nom="Banque")
        MouvementCompte.objects.create(
            compte=compte,
            nature=NatureMouvement.ENCAISSEMENT,
            sens=SensMouvement.ENTREE,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("100000.00"),
            libelle="Encaissement",
        )
        MouvementCompte.objects.create(
            compte=compte,
            nature=NatureMouvement.DECAISSEMENT,
            sens=SensMouvement.SORTIE,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("30000.00"),
            libelle="Décaissement",
        )

        rapprochement = RapprochementService.initialiser(
            compte, date.today(), date.today(), Decimal("70000.00")
        )

        self.assertEqual(rapprochement.solde_comptable, Decimal("70000.00"))
        self.assertEqual(rapprochement.ecart, Decimal("0.00"))


class DashboardSelectorTest(TestCase):
    def test_flux_24h_utilise_le_sens_des_transferts(self):
        compte = Compte.objects.create(code="DASH-001", nom="Dashboard")
        MouvementCompte.objects.create(
            compte=compte,
            nature=NatureMouvement.TRANSFERT,
            sens=SensMouvement.SORTIE,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("30000.00"),
            libelle="Sortie transfert",
        )
        MouvementCompte.objects.create(
            compte=compte,
            nature=NatureMouvement.TRANSFERT,
            sens=SensMouvement.ENTREE,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("10000.00"),
            libelle="Entrée transfert",
        )

        flux = DashboardSelector().flux_24h()

        self.assertEqual(flux["entrees"], Decimal("10000.00"))
        self.assertEqual(flux["sorties"], Decimal("30000.00"))
        self.assertEqual(flux["flux_net"], Decimal("-20000.00"))

    def test_synthese_agrege_les_soldes_par_devise_sans_conversion_magique(self):
        eur = Devise.objects.get(code="EUR")
        Compte.objects.create(code="XOF-001", nom="XOF", solde_actuel=Decimal("500000.00"))
        Compte.objects.create(code="EUR-001", nom="EUR", devise=eur, solde_actuel=Decimal("1000.00"))

        synthese = DashboardSelector().synthese_globale()

        self.assertIsNone(synthese["solde_total"])
        self.assertEqual(synthese["soldes_par_devise"]["XOF"], Decimal("500000.00"))
        self.assertEqual(synthese["soldes_par_devise"]["EUR"], Decimal("1000.00"))


class ConfigurationFinanciereSelectorTest(TestCase):
    def test_cash_only_n_expose_aucune_banque_ni_mobile_money(self):
        cash_provider = FinancialProvider.objects.create(
            code="CASH",
            name="Espèces",
            kind=ProviderKind.CASH,
            country_code="ML",
            logo="providers/ml/cash.svg",
        )
        Compte.objects.create(
            entreprise_id="A",
            code="CAISSE",
            nom="Caisse",
            provider=cash_provider,
            type=TypeCompte.ESPECES,
        )

        configuration = ConfigurationFinanciereSelector(entreprise_id="A").configuration()

        self.assertEqual([account["provider"] for account in configuration["accounts"]], ["CASH"])
        self.assertEqual(configuration["payment_methods"], [])
        self.assertEqual(
            configuration["capabilities"],
            {
                "has_cash": True,
                "has_mobile_money": False,
                "has_bank": False,
                "can_transfer": False,
                "can_reconcile_bank": False,
            },
        )

    def test_mode_inactif_si_son_compte_est_inactif(self):
        provider = FinancialProvider.objects.create(
            code="ORANGE_MONEY",
            name="Orange Money",
            kind=ProviderKind.MOBILE_MONEY,
            country_code="ML",
        )
        compte = Compte.objects.create(
            entreprise_id="A",
            code="OM",
            nom="Orange Money",
            provider=provider,
            type=TypeCompte.MOBILE_MONEY,
            actif=False,
        )
        mode = ModePaiement.objects.create(
            entreprise_id="A",
            code="ORANGE_MONEY",
            libelle="Orange Money",
        )
        mode.comptes.add(compte)

        configuration = ConfigurationFinanciereSelector(entreprise_id="A").configuration()

        self.assertEqual(configuration["accounts"], [])
        self.assertEqual(configuration["payment_methods"], [])


class PermissionServiceTest(TestCase):
    def test_staff_sans_permission_metier_ne_peut_pas_encaisser(self):
        user = User.objects.create_user("staff", password="test", is_staff=True)
        compte = Compte.objects.create(code="PERM-001", nom="Permission")

        with self.assertRaises(PermissionDenied):
            MouvementCompteService.encaisser(
                compte=compte,
                montant=Decimal("1000.00"),
                libelle="Test",
                user=user,
            )
