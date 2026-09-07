from django.conf import settings
from appconf import AppConf


class ComptesAppConf(AppConf):
    """Configuration globale du module comptes.

    Chaque projet peut surcharger dans settings.COMPTES:
        COMPTES = {
            'DEFAULT_CURRENCY': 'XOF',
            'ALLOW_OVERDRAFT': False,
            'AUTO_CREATE_ACCOUNTING_ENTRIES': True,
            'SCOPING_ENABLED': False,
            'ALLOW_BACKDATED_OPERATIONS': False,
            'LOCK_CLOSED_PERIODS': True,
            'EMIT_DOMAIN_EVENTS': True,
        }
    """

    DEFAULT_CURRENCY = "XOF"
    ALLOW_OVERDRAFT = False
    AUTO_CREATE_ACCOUNTING_ENTRIES = True
    SCOPING_ENABLED = False
    ALLOW_BACKDATED_OPERATIONS = False
    LOCK_CLOSED_PERIODS = True
    EMIT_DOMAIN_EVENTS = True

    class Meta:
        prefix = "COMPTES"


def get_comptes_setting(name, default=None):
    """Lit la configuration documentée ``COMPTES = {...}`` de façon centralisée."""
    configured = getattr(settings, "COMPTES", {})
    if name in configured:
        return configured[name]
    return getattr(ComptesAppConf, name, default)


def default_currency():
    return get_comptes_setting("DEFAULT_CURRENCY", "XOF")
