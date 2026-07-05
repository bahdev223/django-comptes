from django.conf import settings
from appconf import AppConf


class ComptesAppConf(AppConf):
    """Configuration globale du module comptes.

    Chaque projet peut surcharger dans settings.COMPTES:
        COMPTES = {
            'DEFAULT_CURRENCY': 'XOF',
            'ALLOW_OVERDRAFT': False,
            'AUTO_CREATE_ACCOUNTING_ENTRIES': True,
            'TENANT_ENABLED': True,
            'TENANT_ID_FIELD': 'tenant_id',
        }
    """

    DEFAULT_CURRENCY = "XOF"
    ALLOW_OVERDRAFT = False
    AUTO_CREATE_ACCOUNTING_ENTRIES = True
    TENANT_ENABLED = True
    TENANT_ID_FIELD = "tenant_id"

    class Meta:
        prefix = "COMPTES"
