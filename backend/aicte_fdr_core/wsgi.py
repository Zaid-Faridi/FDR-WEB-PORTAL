import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aicte_fdr_core.settings')

application = get_wsgi_application()
