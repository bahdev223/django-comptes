"""
Tests unitaires du module comptes.

Execute avec:
    cd django-comptes && python -m pytest tests/ -v
    cd django-comptes && python manage.py test tests/
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model

from comptes.models import (
    Compte, TypeCompte, RoleCompte,
    MouvementCompte, NatureMouvement, StatutMouvement,
    TransfertCompte, JournalCompte, LigneJournalCompte,
    ClotureCompte, PeriodeCloture,
    RapprochementBancaire, StatutRapprochement,
    HistoriqueCompte, TypeChangement, CompteFavori,
)

User = get_user_model()


class CompteModelTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="C-001",
            nom="Caisse Principale",
            type=TypeCompte.ESPECES,
            role=RoleCompte.PRINCIPAL,
            solde_actuel=Decimal("100000.00"),
            compte_comptable_code="5711",
        )

    def test_creation_compte(self):
        self.assertEqual(self.compte.code, "C-001")
        self.assertEqual(self.compte.nom, "Caisse Principale")
        self.assertEqual(self.compte.type, "ESPECES")
        self.assertEqual(self.compte.role, "PRINCIPAL")
        self.assertEqual(self.compte.devise, "XOF")
        self.assertTrue(self.compte.actif)
        self.assertFalse(self.compte.autoriser_decouvert)

    def test_solde_disponible_sans_decouvert(self):
        self.assertEqual(self.compte.solde_disponible, Decimal("100000.00"))

    def test_solde_disponible_avec_decouvert(self):
        self.compte.autoriser_decouvert = True
        self.compte.limite_decouvert = Decimal("50000.00")
        self.assertEqual(self.compte.solde_disponible, Decimal("150000.00"))

    def test_est_a_decouvert(self):
        self.assertFalse(self.compte.est_a_decouvert)
        self.compte.solde_actuel = Decimal("-10000.00")
        self.compte.autoriser_decouvert = True
        self.assertTrue(self.compte.est_a_decouvert)

    def test_proprietes_type(self):
        self.assertTrue(self.compte.est_caisse)
        self.assertFalse(self.compte.est_banque)
        self.assertFalse(self.compte.est_mobile_money)

    def test_string_representation(self):
        self.assertEqual(str(self.compte), "C-001 - Caisse Principale")


class MouvementCompteModelTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="MM-001", nom="Orange Money",
            type=TypeCompte.MOBILE_MONEY,
            solde_actuel=Decimal("50000.00"),
            compte_comptable_code="5811",
        )
        self.user = User.objects.create_user("testuser", password="test")

    def test_creation_mouvement(self):
        mvt = MouvementCompte.objects.create(
            compte=self.compte,
            nature=NatureMouvement.ENCAISSEMENT,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("25000.00"),
            libelle="Depot mobile money",
            created_by=self.user,
        )
        self.assertEqual(mvt.montant, Decimal("25000.00"))
        self.assertEqual(mvt.nature, "ENCAISSEMENT")
        self.assertEqual(mvt.statut, "VALIDE")
        self.assertTrue(mvt.est_entree)
        self.assertFalse(mvt.est_sortie)

    def test_annulation(self):
        mvt = MouvementCompte.objects.create(
            compte=self.compte,
            nature=NatureMouvement.ENCAISSEMENT,
            statut=StatutMouvement.VALIDE,
            montant=Decimal("10000.00"),
            libelle="Test",
        )
        self.assertTrue(mvt.est_entree)

    def test_statuts_mouvement(self):
        for statut in [s[0] for s in StatutMouvement.choices]:
            mvt = MouvementCompte.objects.create(
                compte=self.compte,
                nature=NatureMouvement.ENCAISSEMENT,
                statut=statut,
                montant=Decimal("1000.00"),
                libelle=f"Test {statut}",
            )
            self.assertEqual(mvt.statut, statut)


class TransfertCompteModelTest(TestCase):
    def setUp(self):
        self.source = Compte.objects.create(
            code="SRC-001", nom="Source",
            solde_actuel=Decimal("100000.00"),
        )
        self.dest = Compte.objects.create(
            code="DST-001", nom="Destination",
        )

    def test_creation_transfert(self):
        t = TransfertCompte.objects.create(
            source=self.source,
            destination=self.dest,
            montant=Decimal("30000.00"),
            reference="TRF-001",
            notes="Virement quotidien",
        )
        self.assertEqual(t.montant, Decimal("30000.00"))
        self.assertIn("SRC-001", str(t))
        self.assertIn("DST-001", str(t))


class JournalCompteModelTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="JRN-001", nom="Test Journal",
            solde_actuel=Decimal("50000.00"),
        )

    def test_journal_creation(self):
        journal = JournalCompte.objects.create(
            compte=self.compte,
            solde_ouverture=Decimal("40000.00"),
            total_entrees=Decimal("15000.00"),
            total_sorties=Decimal("5000.00"),
            solde_theorique=Decimal("50000.00"),
            solde_reel=Decimal("50000.00"),
            ecart=Decimal("0.00"),
            cloture=True,
        )
        self.assertTrue(journal.cloture)
        self.assertEqual(journal.ecart, Decimal("0.00"))

    def test_ligne_journal(self):
        journal = JournalCompte.objects.create(
            compte=self.compte,
            solde_ouverture=Decimal("0.00"),
            solde_theorique=Decimal("10000.00"),
            solde_reel=Decimal("10000.00"),
        )
        ligne = LigneJournalCompte.objects.create(
            journal=journal,
            type_operation="Vente",
            nature=NatureMouvement.ENCAISSEMENT,
            montant=Decimal("10000.00"),
            sens="ENTREE",
            libelle="Test ligne",
        )
        self.assertEqual(ligne.montant, Decimal("10000.00"))


class ClotureCompteModelTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="CLT-001", nom="Test Cloture",
        )

    def test_cloture_quotidienne(self):
        cloture = ClotureCompte.objects.create(
            compte=self.compte,
            periode=PeriodeCloture.QUOTIDIENNE,
            date_cloture=date.today(),
            solde_avant=Decimal("50000.00"),
            solde_apres=Decimal("50000.00"),
        )
        self.assertEqual(cloture.solde_avant, cloture.solde_apres)

    def test_cloture_avec_ecart(self):
        cloture = ClotureCompte.objects.create(
            compte=self.compte,
            periode=PeriodeCloture.QUOTIDIENNE,
            date_cloture=date.today(),
            solde_avant=Decimal("50000.00"),
            solde_apres=Decimal("48000.00"),
            ecart=Decimal("-2000.00"),
            commentaire="Ecart de caisse constate",
        )
        self.assertEqual(cloture.ecart, Decimal("-2000.00"))


class RapprochementBancaireModelTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="BQ-001", nom="BICICI",
            type=TypeCompte.BANQUE,
        )

    def test_rapprochement_equilibre(self):
        rapp = RapprochementBancaire.objects.create(
            compte=self.compte,
            date_debut=date.today() - timedelta(days=30),
            date_fin=date.today(),
            date_releve=date.today(),
            solde_releve=Decimal("100000.00"),
            solde_comptable=Decimal("100000.00"),
            ecart=Decimal("0.00"),
            statut=StatutRapprochement.EQUILIBRE,
        )
        self.assertEqual(rapp.ecart, Decimal("0.00"))
        self.assertEqual(rapp.statut, "EQUILIBRE")


class HistoriqueCompteModelTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="HST-001", nom="Historique Test",
        )
        self.user = User.objects.create_user("admin", password="admin")

    def test_historique_compte(self):
        h = HistoriqueCompte.objects.create(
            compte=self.compte,
            type_changement=TypeChangement.NOM,
            ancienne_valeur="Ancien Nom",
            nouvelle_valeur="Nouveau Nom",
            commentaire="Renommage",
            modifie_par=self.user,
        )
        self.assertEqual(h.type_changement, "NOM")
        self.assertIn("Ancien Nom", str(h))
