from django.apps import AppConfig

class BankAdaptersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.bank_adapters'
    verbose_name = 'Pluggable Bank Verification Adapters'
