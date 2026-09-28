import importlib
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TenantDataMigrationTest(TransactionTestCase):
    migrate_to = ("comptes", "0008_harden_tenant_integrity")

    def test_forward_migration_preserve_m2m_et_backfill_tenant(self):
        executor = MigrationExecutor(connection)
        historical_apps = executor.loader.project_state([self.migrate_to]).apps

        Compte = historical_apps.get_model("comptes", "Compte")
        ModePaiement = historical_apps.get_model("comptes", "ModePaiement")
        MouvementCompte = historical_apps.get_model("comptes", "MouvementCompte")

        compte = Compte.objects.create(
            entreprise_id="TENANT-A",
            code="MIG-CASH",
            nom="Caisse migration",
            solde_actuel=Decimal("100.00"),
        )
        mode = ModePaiement.objects.create(
            entreprise_id="",
            code="MIG-CASH",
            libelle="Espèces migration",
        )
        mouvement = MouvementCompte.objects.create(
            compte=compte,
            entreprise_id="",
            montant=Decimal("10.00"),
            libelle="Ancien mouvement migration",
        )

        quote = connection.ops.quote_name
        legacy = "comptes_modepaiement_comptes"
        tables = set(connection.introspection.table_names())
        if legacy in tables:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE {quote(legacy)}")

        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE {quote(legacy)} ("
                "id INTEGER PRIMARY KEY, "
                "modepaiement_id BIGINT NOT NULL, "
                "compte_id BIGINT NOT NULL)"
            )
            cursor.execute(
                f"INSERT INTO {quote(legacy)} "
                "(id, modepaiement_id, compte_id) VALUES (%s, %s, %s)",
                [1, mode.pk, compte.pk],
            )

        migration_module = importlib.import_module(
            "comptes.migrations.0008_harden_tenant_integrity"
        )
        with connection.schema_editor() as schema_editor:
            migration_module.forwards(historical_apps, schema_editor)

        mode.refresh_from_db()
        mouvement.refresh_from_db()

        self.assertEqual(mode.entreprise_id, "TENANT-A")
        self.assertEqual(mode.comptes.count(), 1)
        self.assertEqual(mode.comptes.get().entreprise_id, "TENANT-A")
        self.assertEqual(mouvement.entreprise_id, "TENANT-A")
        self.assertNotIn(legacy, connection.introspection.table_names())
