import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aicte_fdr_core.settings')

app = Celery('aicte_fdr_core')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
