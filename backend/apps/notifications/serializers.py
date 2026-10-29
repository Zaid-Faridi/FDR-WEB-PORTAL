from rest_framework import serializers
from apps.notifications.models import (
    Notification,
    ReminderRule,
    EscalationRule,
    EscalationRecord,
)


class NotificationSerializer(serializers.ModelSerializer):
    instrument_reference = serializers.CharField(source='instrument.reference_number', read_only=True)
    institution_name = serializers.CharField(source='instrument.institution.name', read_only=True, default='')

    class Meta:
        model = Notification
        fields = [
            'id',
            'instrument',
            'instrument_reference',
            'institution_name',
            'recipient',
            'recipient_role',
            'recipient_email',
            'recipient_phone',
            'channel',
            'notification_type',
            'title',
            'message',
            'offset_days',
            'escalation_level',
            'dedup_key',
            'is_read',
            'sent_at',
            'read_at',
        ]
        read_only_fields = ['id', 'sent_at', 'read_at', 'dedup_key']


class ReminderRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderRule
        fields = [
            'id',
            'name',
            'offset_days',
            'channel',
            'target_role',
            'template_subject',
            'template_body',
            'is_active',
            'created_at',
            'updated_at',
        ]


class EscalationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscalationRule
        fields = [
            'id',
            'name',
            'trigger_condition',
            'wait_period_days',
            'from_level',
            'to_level',
            'channel',
            'template_subject',
            'template_body',
            'is_active',
            'created_at',
            'updated_at',
        ]


class EscalationRecordSerializer(serializers.ModelSerializer):
    instrument_reference = serializers.CharField(source='instrument.reference_number', read_only=True)
    institution_name = serializers.CharField(source='instrument.institution.name', read_only=True, default='')

    class Meta:
        model = EscalationRecord
        fields = [
            'id',
            'instrument',
            'instrument_reference',
            'institution_name',
            'rule',
            'trigger_condition',
            'from_level',
            'to_level',
            'reason',
            'triggered_at',
            'is_resolved',
            'resolved_at',
            'resolution_note',
        ]


class SimulatedDateRequestSerializer(serializers.Serializer):
    simulated_date = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Target date in 'YYYY-MM-DD' format or null to clear simulation."
    )
