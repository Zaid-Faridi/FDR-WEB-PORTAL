from rest_framework import serializers
from .models import AuditLog, AuditEntry

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


class AuditEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEntry
        fields = [
            'id',
            'timestamp',
            'actor',
            'actor_username',
            'role',
            'action',
            'object_type',
            'object_id',
            'object_repr',
            'before_values',
            'after_values',
            'ip_address',
            'user_agent',
            'previous_hash',
            'entry_hash',
        ]
        read_only_fields = fields

