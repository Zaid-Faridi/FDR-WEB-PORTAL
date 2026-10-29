from rest_framework import serializers
from .models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'timestamp',
            'actor_username',
            'actor_role',
            'action',
            'entity_type',
            'entity_id',
            'previous_state',
            'new_state',
            'ip_address',
            'metadata',
        ]
        read_only_fields = fields
