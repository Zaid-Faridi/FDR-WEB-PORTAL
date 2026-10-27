import redis
from datetime import datetime
from django.conf import settings
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.bank_adapters.factory import get_bank_adapter

from rest_framework import permissions

class HealthCheckView(APIView):
    """
    Health check endpoint returning overall system status,
    database connectivity, redis queue connectivity,
    and active bank verification adapter information.
    """
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'AICTE FDR / Security Deposit Management Core API',
            'version': '1.0.0-hackathon.scaffold',
            'checks': {
                'database': False,
                'redis': False,
            },
            'bank_verification_adapter': {
                'name': 'Unknown',
                'is_mock': True,
                'class': settings.BANK_ADAPTER_CLASS,
            }
        }

        # Check database
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1;')
                row = cursor.fetchone()
                if row and row[0] == 1:
                    health_status['checks']['database'] = True
        except Exception as exc:
            health_status['status'] = 'degraded'
            health_status['checks']['database_error'] = str(exc)

        # Check redis
        try:
            r = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=1)
            if r.ping():
                health_status['checks']['redis'] = True
        except Exception as exc:
            health_status['status'] = 'degraded'
            health_status['checks']['redis_error'] = str(exc)

        # Bank adapter info
        try:
            adapter = get_bank_adapter()
            health_status['bank_verification_adapter']['name'] = adapter.adapter_name
            health_status['bank_verification_adapter']['is_mock'] = adapter.is_mock
        except Exception as exc:
            health_status['bank_verification_adapter']['error'] = str(exc)

        http_status = status.HTTP_200_OK if health_status['status'] == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(health_status, status=http_status)
