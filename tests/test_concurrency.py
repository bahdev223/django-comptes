import threading
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from comptes.models import Compte, MouvementCompte
from comptes.services import MouvementCompteService


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Test de concurrence réservé à PostgreSQL")
class MovementConcurrencyTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.compte = Compte.objects.create(
            entreprise_id="A",
            code="CONCURRENT",
            nom="Caisse concurrence",
            solde_actuel=Decimal("50000.00"),
        )
        self.user = User.objects.create_user("concurrent-user", password="test")
        self.user.user_permissions.add(Permission.objects.get(codename="encaisser"))

    def test_deux_retries_concurrents_ne_creent_qu_un_mouvement(self):
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def worker():
            close_old_connections()
            try:
                compte = Compte.objects.get(pk=self.compte.pk)
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                mouvement = MouvementCompteService.encaisser(
                    compte=compte,
                    montant=Decimal("10000.00"),
                    libelle="Retry concurrent",
                    user=user,
                    idempotency_key="concurrent-payment-1",
                )
                results.append(mouvement.pk)
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(
            MouvementCompte.objects.filter(
                entreprise_id="A",
                idempotency_key="concurrent-payment-1",
            ).count(),
            1,
        )
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_actuel, Decimal("60000.00"))
