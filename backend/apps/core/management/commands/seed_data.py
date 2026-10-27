from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.institutions.models import Institution, InstitutionStatus
from apps.instruments.models import Instrument, InstrumentStatus, InstrumentType, FieldSource
from apps.common.models import DataProvenanceSource
from apps.common.audit import record_audit_event
from apps.users.models import UserRole

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds initial institutions, users across all roles, and demonstration instruments'

    def handle(self, *args, **options):
        self.stdout.write("Initializing AICTE FDR Portal Phase 1 Seed Data...")

        with transaction.atomic():
            # 1. Institutions
            inst_delhi, _ = Institution.objects.get_or_create(
                aicte_id='1-100200300',
                defaults={
                    'name': 'Delhi Institute of Technology & Management',
                    'institution_type': 'Engineering & Technology',
                    'address': 'Sector 14, Dwarka',
                    'state': 'Delhi',
                    'district': 'South West Delhi',
                    'pincode': '110078',
                    'status': InstitutionStatus.ACTIVE,
                    'contact_email': 'registrar@ditm-delhi.edu.in',
                    'contact_phone': '+91-11-28080001',
                }
            )

            inst_mumbai, _ = Institution.objects.get_or_create(
                aicte_id='1-400500600',
                defaults={
                    'name': 'Mumbai College of Engineering & Research',
                    'institution_type': 'Engineering & Technology',
                    'address': 'Bandra Kurla Complex',
                    'state': 'Maharashtra',
                    'district': 'Mumbai Suburban',
                    'pincode': '400051',
                    'status': InstitutionStatus.ACTIVE,
                    'contact_email': 'principal@mumbai-engg.edu.in',
                    'contact_phone': '+91-22-26590002',
                }
            )

            # 2. Users for all 4 roles
            # Role: ADMIN
            admin_user, _ = User.objects.get_or_create(
                username='aicte_admin',
                defaults={
                    'email': 'admin@aicte-india.org',
                    'role': UserRole.ADMIN,
                    'is_staff': True,
                    'is_superuser': True,
                    'first_name': 'Regulation Bureau',
                    'last_name': 'Admin',
                    'designation': 'System Director',
                }
            )
            admin_user.set_password('Admin@AICTE2026')
            admin_user.save()

            # Role: SCRUTINY_OFFICER
            officer_user, _ = User.objects.get_or_create(
                username='officer_sharma',
                defaults={
                    'email': 'r.sharma@aicte-india.org',
                    'role': UserRole.SCRUTINY_OFFICER,
                    'first_name': 'Rajesh',
                    'last_name': 'Sharma',
                    'designation': 'Senior Scrutiny Officer',
                }
            )
            officer_user.set_password('Officer@AICTE2026')
            officer_user.save()

            # Role: APPROVING_AUTHORITY
            approver_user, _ = User.objects.get_or_create(
                username='approver_verma',
                defaults={
                    'email': 'v.verma@aicte-india.org',
                    'role': UserRole.APPROVING_AUTHORITY,
                    'first_name': 'Vikram',
                    'last_name': 'Verma',
                    'designation': 'Bureau Advisor & Member Secretary Nominee',
                }
            )
            approver_user.set_password('Approver@AICTE2026')
            approver_user.save()

            # Role: INSTITUTION (Delhi Institute)
            inst_user_delhi, _ = User.objects.get_or_create(
                username='user_ditm',
                defaults={
                    'email': 'fdr.cell@ditm-delhi.edu.in',
                    'role': UserRole.INSTITUTION,
                    'institution': inst_delhi,
                    'first_name': 'Amit',
                    'last_name': 'Gupta',
                    'designation': 'Finance Registrar',
                }
            )
            inst_user_delhi.set_password('College@DITM2026')
            inst_user_delhi.save()

            # Role: INSTITUTION (Mumbai College)
            inst_user_mumbai, _ = User.objects.get_or_create(
                username='user_mumbai',
                defaults={
                    'email': 'admin@mumbai-engg.edu.in',
                    'role': UserRole.INSTITUTION,
                    'institution': inst_mumbai,
                    'first_name': 'Sanjay',
                    'last_name': 'Deshmukh',
                    'designation': 'Accounts Officer',
                }
            )
            inst_user_mumbai.set_password('College@Mumbai2026')
            inst_user_mumbai.save()

            # 3. Demonstration Instrument
            fdr1, created = Instrument.objects.get_or_create(
                reference_number='FDR-SBI-2024-DELHI-001',
                defaults={
                    'institution': inst_delhi,
                    'instrument_type': InstrumentType.FDR,
                    'issuing_bank': 'State Bank of India',
                    'issuing_branch': 'Dwarka Sector 10 Branch',
                    'branch_ifsc': 'SBIN0011566',
                    'amount': 1500000.00,
                    'issue_date': date(2024, 6, 15),
                    'maturity_date': date(2032, 6, 15),
                    'lien_in_favour_of_aicte': True,
                    'joint_holder_name': 'Delhi Institute of Tech and Member Secretary AICTE',
                    'status': InstrumentStatus.SUBMITTED,
                    'created_by': inst_user_delhi,
                }
            )

            if created:
                # Add FieldSource entries
                FieldSource.objects.create(
                    instrument=fdr1,
                    field_name='amount',
                    field_value='1500000.00',
                    value_source=DataProvenanceSource.INSTITUTION_SUBMITTED,
                    is_confirmed=False
                )
                FieldSource.objects.create(
                    instrument=fdr1,
                    field_name='lien_in_favour_of_aicte',
                    field_value='True',
                    value_source=DataProvenanceSource.INSTITUTION_SUBMITTED,
                    is_confirmed=False
                )

                record_audit_event(
                    action='INSTRUMENT_SEEDED',
                    entity_type='Instrument',
                    entity_id=str(fdr1.id),
                    actor_username='seed_script',
                    actor_role='ADMIN',
                    previous_state={},
                    new_state={'reference_number': fdr1.reference_number, 'status': fdr1.status},
                )

            # Record overall bootstrap audit
            record_audit_event(
                action='PHASE_1_SEEDED',
                entity_type='SystemConfiguration',
                entity_id='PHASE-1-BOOTSTRAP',
                actor_username='seed_script',
                actor_role='ADMIN',
                previous_state={},
                new_state={
                    'institutions': [inst_delhi.aicte_id, inst_mumbai.aicte_id],
                    'roles_seeded': ['ADMIN', 'SCRUTINY_OFFICER', 'APPROVING_AUTHORITY', 'INSTITUTION'],
                }
            )

        self.stdout.write(self.style.SUCCESS("✓ Seeded Institutions: DITM Delhi (1-100200300), Mumbai College (1-400500600)"))
        self.stdout.write(self.style.SUCCESS("✓ Seeded Users: aicte_admin, officer_sharma, approver_verma, user_ditm, user_mumbai"))
        self.stdout.write(self.style.SUCCESS("✓ Seeded Sample Instrument: FDR-SBI-2024-DELHI-001"))
