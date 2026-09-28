from django.core.management.base import BaseCommand

from comptes.services import FinancialProviderService


class Command(BaseCommand):
    help = "Synchronise le référentiel des prestataires financiers maliens."

    def handle(self, *args, **options):
        result = FinancialProviderService.synchroniser_mali()
        self.stdout.write(
            self.style.SUCCESS(
                f"Providers Mali synchronisés: {result['count']} (version {result['version']})"
            )
        )
