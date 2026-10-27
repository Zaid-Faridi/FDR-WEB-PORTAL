from rest_framework import serializers
from .models import Instrument, Document, FieldSource, Remark, InstrumentStatus
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


class InstrumentSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    institution_aicte_id = serializers.CharField(source='institution.aicte_id', read_only=True)
    field_sources = FieldSourceSerializer(many=True, read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    remarks = serializers.SerializerMethodField()
    claimed_vs_confirmed = serializers.SerializerMethodField()

    class Meta:
        model = Instrument
        fields = [
            'id',
            'institution',
            'institution_name',
            'institution_aicte_id',
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
            'field_sources',
            'documents',
            'remarks',
            'claimed_vs_confirmed',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

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


from apps.institutions.models import Institution

class InstrumentCreateSerializer(serializers.ModelSerializer):
    institution = serializers.PrimaryKeyRelatedField(
        required=False,
        queryset=Institution.objects.all()
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
        return attrs


class VerifyActionSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class DiscrepancyActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True)
    field_name = serializers.CharField(required=False, allow_blank=True, default='')


class ReleaseDecisionSerializer(serializers.Serializer):
    decision_notes = serializers.CharField(required=False, allow_blank=True, default='')
    noc_reference = serializers.CharField(required=False, allow_blank=True, default='')
