from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TenantDataMigrationTest(TransactionTestCase):
    migrate_from = ("comptes", "0006_financial_provider_compte_provider")
    migrate_to = ("comptes", "0008_harden_tenant_integrity")

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps

        Compte = old_apps.get_model("comptes", "Compte")
        ModePaiement = old_apps.get_model("comptes", "ModePaiement")
        MouvementCompte = old_apps.get_model("comptes", "MouvementCompte")

        compte = Compte.objects.create(
            entreprise_id="TENANT-A",
            code="CASH",
            nom="Caisse",
            solde_actuel=Decimal("100.00"),
        )
        mode = ModePaiement.objects.create(code="CASH", libelle="Espèces")
        mode.comptes.add(compte)
        MouvementCompte.objects.create(
            compte=compte,
            montant=Decimal("10.00"),
            libelle="Ancien mouvement",
        )

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        super().tearDown()

    def test_migration_preserve_m2m_et_backfill_tenant(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        apps = self.executor.loader.project_state([self.migrate_to]).apps

        ModePaiement = apps.get_model("comptes", "ModePaiement")
        MouvementCompte = apps.get_model("comptes", "MouvementCompte")

        mode = ModePaiement.objects.get(code="CASH")
        mouvement = MouvementCompte.objects.get(libelle="Ancien mouvement")

        self.assertEqual(mode.entreprise_id, "TENANT-A")
        self.assertEqual(mode.comptes.count(), 1)
        self.assertEqual(
            mode.comptes.get().entreprise_id,
            "TENANT-A",
        )
        self.assertEqual(mouvement.entreprise_id, "TENANT-A")
