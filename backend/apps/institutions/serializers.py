from rest_framework import serializers
from .models import Institution

class InstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = [
            'id',
            'aicte_id',
            'name',
            'institution_type',
            'address',
            'state',
            'district',
            'pincode',
            'status',
            'contact_email',
            'contact_phone',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
