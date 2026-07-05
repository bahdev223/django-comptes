from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ComptesConfig(AppConfig):
    name = "comptes"
    verbose_name = _("Comptes Financiers")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals
