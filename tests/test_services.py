"""
Tests des services metier du module comptes.
"""

from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model

from comptes.models import (
    Compte, TypeCompte, MouvementCompte,
    NatureMouvement, StatutMouvement, TransfertCompte,
    JournalCompte, ClotureCompte,
)
from comptes.services import (
    CompteService, MouvementCompteService,
    TransfertCompteService, ClotureCompteService,
    JournalCompteService,
)

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


class MouvementCompteServiceTest(TestCase):
    def setUp(self):
        self.compte = Compte.objects.create(
            code="MVT-001", nom="Test Mouvements",
            solde_actuel=Decimal("50000.00"),
        )
        self.user = User.objects.create_user("caissier", password="test")

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
        self.user = User.objects.create_user("gerant", password="test")

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
