from rest_framework import serializers
from .models import Instrument, Document, FieldSource, Remark, InstrumentStatus, SavedFilter
from apps.common.models import DataProvenanceSource

class FieldSourceSerializer(serializers.ModelSerializer):
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True)

    class Meta:
        model = FieldSource
        fields = [
            'id',
            'field_name',
            'field_value',
            'value_source',
            'verified_at',
            'verified_by',
            'verified_by_username',
            'source_reference',
            'is_confirmed',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    duplicate_of_reference = serializers.CharField(source='duplicate_of.instrument.reference_number', read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id',
            'instrument',
            'document_type',
            'file_name',
            'mime_type',
            'sha256_hash',
            'file_size_bytes',
            'version',
            'is_current_version',
            'is_encrypted',
            'is_duplicate_hash',
            'duplicate_of',
            'duplicate_of_reference',
            'uploaded_by',
            'uploaded_by_username',
            'uploaded_at',
            'download_url',
        ]
        read_only_fields = fields

    def get_download_url(self, obj):
        return f"/api/documents/{obj.id}/download/"


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    document_type = serializers.ChoiceField(choices=Document.DOCUMENT_TYPES, default='FDR_CERTIFICATE')


class RemarkSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Remark
        fields = [
            'id',
            'instrument',
            'author',
            'author_username',
            'role',
            'remark_type',
            'text',
            'is_internal',
            'created_at',
        ]
        read_only_fields = ['id', 'author', 'role', 'created_at']


class DiscrepancySerializer(serializers.ModelSerializer):
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True)

    class Meta:
        from .models import Discrepancy
        model = Discrepancy
        fields = [
            'id',
            'instrument',
            'rule_code',
            'severity',
            'title',
            'description',
            'details',
            'is_resolved',
            'resolved_by',
            'resolved_by_username',
            'resolved_at',
            'resolution_note',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class InstrumentSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    institution_aicte_id = serializers.CharField(source='institution.aicte_id', read_only=True)
    institution_type = serializers.CharField(source='institution.institution_type', read_only=True)
    field_sources = FieldSourceSerializer(many=True, read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    discrepancies = DiscrepancySerializer(many=True, read_only=True)
    remarks = serializers.SerializerMethodField()
    claimed_vs_confirmed = serializers.SerializerMethodField()
    replaces_reference = serializers.CharField(source='replaces.reference_number', read_only=True)
    released_by_username = serializers.CharField(source='released_by.username', read_only=True)
    replacement_chain = serializers.SerializerMethodField()
    release_checklist = serializers.SerializerMethodField()

    class Meta:
        model = Instrument
        fields = [
            'id',
            'institution',
            'institution_name',
            'institution_aicte_id',
            'institution_type',
            'instrument_type',
            'reference_number',
            'issuing_bank',
            'issuing_branch',
            'branch_ifsc',
            'amount',
            'issue_date',
            'maturity_date',
            'lien_in_favour_of_aicte',
            'joint_holder_name',
            'status',
            'trust_score',
            'ocr_extracted_data',
            'replaces',
            'replaces_reference',
            'renewal_type',
            'replacement_chain',
            'release_checklist',
            'release_requested_at',
            'release_justification',
            'scrutiny_recommended_at',
            'scrutiny_recommendation',
            'scrutiny_notes',
            'released_at',
            'released_by',
            'released_by_username',
            'release_order_reference',
            'rejection_reason',
            'compliance_hold',
            'compliance_hold_reason',
            'field_sources',
            'documents',
            'discrepancies',
            'remarks',
            'claimed_vs_confirmed',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'trust_score', 'created_by', 'created_at', 'updated_at',
            'released_at', 'released_by', 'released_by_username', 'scrutiny_recommended_at',
            'release_requested_at'
        ]

    def get_remarks(self, obj):
        request = self.context.get('request')
        qs = obj.remarks.all()
        # If user is from Institution role, hide internal notes
        if request and getattr(request.user, 'role', None) == 'INSTITUTION':
            qs = qs.filter(is_internal=False)
        return RemarkSerializer(qs, many=True).data

    def get_claimed_vs_confirmed(self, obj):
        """
        Builds a UI-ready comparison structure distinguishing claimed vs confirmed.
        """
        sources = obj.field_sources.all()
        result = {}
        for fs in sources:
            name = fs.field_name
            if name not in result:
                result[name] = {'claimed': None, 'confirmed': None}
            if fs.value_source == DataProvenanceSource.INSTITUTION_SUBMITTED:
                result[name]['claimed'] = {
                    'value': fs.field_value,
                    'created_at': fs.created_at,
                }
            elif fs.value_source == DataProvenanceSource.BANK_CONFIRMED:
                result[name]['confirmed'] = {
                    'value': fs.field_value,
                    'verified_at': fs.verified_at,
                    'source_reference': fs.source_reference,
                    'is_confirmed': fs.is_confirmed,
                }
        return result

    def get_replacement_chain(self, obj):
        return obj.get_replacement_chain()

    def get_release_checklist(self, obj):
        return obj.evaluate_release_checklist()


from apps.institutions.models import Institution

class InstrumentCreateSerializer(serializers.ModelSerializer):
    institution = serializers.PrimaryKeyRelatedField(
        required=False,
        queryset=Institution.objects.all()
    )
    replaces = serializers.PrimaryKeyRelatedField(
        queryset=Instrument.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Instrument
        fields = [
            'id',
            'institution',
            'instrument_type',
            'reference_number',
            'issuing_bank',
            'issuing_branch',
            'branch_ifsc',
            'amount',
            'issue_date',
            'maturity_date',
            'lien_in_favour_of_aicte',
            'joint_holder_name',
            'status',
            'replaces',
            'renewal_type',
        ]
        read_only_fields = ['id', 'status']

    def validate(self, attrs):
        request = self.context.get('request')
        # If institution user, force institution to user's assigned institution
        if request and getattr(request.user, 'role', None) == 'INSTITUTION':
            if not request.user.institution:
                raise serializers.ValidationError("Your user account has no associated technical institution.")
            attrs['institution'] = request.user.institution
        elif 'institution' not in attrs:
            raise serializers.ValidationError({"institution": "Institution is required."})

        # Validate replacement belongs to same institution
        replaces = attrs.get('replaces')
        inst = attrs.get('institution')
        if replaces and inst and replaces.institution_id != inst.id:
            raise serializers.ValidationError({"replaces": "The predecessor instrument must belong to the same institution."})

        return attrs


class VerifyActionSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class DiscrepancyActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True)
    field_name = serializers.CharField(required=False, allow_blank=True, default='')
    severity = serializers.ChoiceField(choices=['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'], default='HIGH')


class ResolveDiscrepancySerializer(serializers.Serializer):
    resolution_note = serializers.CharField(required=True)


class OCRScanRequestSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)


class ReleaseDecisionSerializer(serializers.Serializer):
    decision_notes = serializers.CharField(required=False, allow_blank=True, default='')
    noc_reference = serializers.CharField(required=False, allow_blank=True, default='')


class ReleaseRequestSerializer(serializers.Serializer):
    justification = serializers.CharField(required=True, allow_blank=False)


class ScrutinizeReleaseSerializer(serializers.Serializer):
    recommendation = serializers.ChoiceField(
        choices=['RECOMMEND_APPROVAL', 'RECOMMEND_REJECTION'],
        default='RECOMMEND_APPROVAL'
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class ApproveReleaseSerializer(serializers.Serializer):
    release_order_reference = serializers.CharField(required=True, allow_blank=False)
    decision_notes = serializers.CharField(required=False, allow_blank=True, default='')


class RejectReleaseSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(required=True, allow_blank=False)


class ComplianceHoldSerializer(serializers.Serializer):
    compliance_hold = serializers.BooleanField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default='')


class SavedFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedFilter
        fields = ['id', 'user', 'name', 'filter_params', 'is_default', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def create(self, validated_data):
        user = validated_data.get('user') or self.context['request'].user
        validated_data['user'] = user
        if validated_data.get('is_default'):
            SavedFilter.objects.filter(user=user).update(is_default=False)
        return SavedFilter.objects.create(**validated_data)

    def update(self, instance, validated_data):
        user = self.context['request'].user
        if validated_data.get('is_default'):
            SavedFilter.objects.filter(user=user).exclude(pk=instance.pk).update(is_default=False)
        return super().update(instance, validated_data)

