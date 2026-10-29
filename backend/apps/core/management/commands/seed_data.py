import os
import io
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.institutions.models import Institution, InstitutionStatus
from apps.instruments.models import (
    Instrument,
    InstrumentStatus,
    InstrumentType,
    FieldSource,
    Document,
    Remark,
    Discrepancy,
    DiscrepancySeverity,
)
from apps.notifications.models import (
    ReminderRule,
    EscalationRule,
    EscalationCondition,
    Notification,
    NotificationChannel,
    NotificationType,
)
from apps.common.models import DataProvenanceSource, AuditEntry
from apps.common.audit import record_audit_event
from apps.common.dates import get_effective_date
from apps.users.models import UserRole

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds 25 Technical Institutions and ~60 Instruments covering all lifecycle scenarios (Phase 8)'

    def handle(self, *args, **options):
        self.stdout.write("==========================================================")
        self.stdout.write("Seeding AICTE FDR Portal: 25 Institutions & ~60 Instruments")
        self.stdout.write("==========================================================")

        with transaction.atomic():
            # 1. Base Users
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

            # 2. Seed 25 Technical Institutions across India
            INSTITUTION_DATA = [
                ('1-100200300', 'Delhi Institute of Technology & Management', 'Engineering & Technology', 'Delhi', 'South West Delhi', '110078', 'user_ditm'),
                ('1-400500600', 'Mumbai College of Engineering & Research', 'Engineering & Technology', 'Maharashtra', 'Mumbai Suburban', '400051', 'user_mumbai'),
                ('1-700800900', 'Bangalore National Institute of Applied Sciences', 'Engineering & Technology', 'Karnataka', 'Bangalore Urban', '560100', 'user_bnias'),
                ('1-900100200', 'Chennai Institute of Engineering & Robotics', 'Engineering & Technology', 'Tamil Nadu', 'Chennai', '600119', 'user_cier'),
                ('1-550660770', 'Pune College of Pharmaceutical Sciences', 'Pharmacy', 'Maharashtra', 'Pune', '411038', 'user_pcps'),
                ('1-880990110', 'Hyderabad Global Institute of Management Studies', 'Management', 'Telangana', 'Hyderabad', '500081', 'user_hgims'),
                ('1-110220330', 'Kolkata Institute of Polytechnic & Technology', 'Applied Arts & Crafts', 'West Bengal', 'Kolkata', '700091', 'user_kipt'),
                ('1-440550660', 'Ahmedabad Advanced School of Architecture', 'Architecture & Planning', 'Gujarat', 'Ahmedabad', '380009', 'user_aasa'),
                ('1-770880990', 'Lucknow Apex Institute of Engineering', 'Engineering & Technology', 'Uttar Pradesh', 'Lucknow', '226021', 'user_laie'),
                ('1-330440550', 'Jaipur Royal Polytechnic & Skill Academy', 'Engineering & Technology', 'Rajasthan', 'Jaipur', '302017', 'user_jrps'),
                ('1-660770880', 'Bhopal Central Institute of Technology', 'Engineering & Technology', 'Madhya Pradesh', 'Bhopal', '462003', 'user_bcit'),
                ('1-220330440', 'Chandigarh Northern Engineering Academy', 'Engineering & Technology', 'Chandigarh', 'Chandigarh', '160019', 'user_cnea'),
                ('1-990110220', 'Thiruvananthapuram Institute of Management Studies', 'Management', 'Kerala', 'Thiruvananthapuram', '695016', 'user_tims'),
                ('1-120340560', 'Bhubaneswar Premier Institute of Engineering', 'Engineering & Technology', 'Odisha', 'Khordha', '751024', 'user_bpie'),
                ('1-780910230', 'Patna Magadh Institute of Technical Education', 'Engineering & Technology', 'Bihar', 'Patna', '800001', 'user_pmie'),
                ('1-450670890', 'Guwahati Brahmaputra Engineering College', 'Engineering & Technology', 'Assam', 'Kamrup', '781014', 'user_gbec'),
                ('1-890120340', 'Ranchi Chotanagpur Institute of Technology', 'Engineering & Technology', 'Jharkhand', 'Ranchi', '834001', 'user_rcit'),
                ('1-230450670', 'Dehradun Himalayan School of Computer Studies', 'MCA', 'Uttarakhand', 'Dehradun', '248001', 'user_dhsc'),
                ('1-670890120', 'Shimla Alpine Polytechnic Institute', 'Engineering & Technology', 'Himachal Pradesh', 'Shimla', '171001', 'user_sapi'),
                ('1-340560780', 'Panaji Coastal Institute of Management & Hotel Mgmt', 'Hotel Management', 'Goa', 'North Goa', '403001', 'user_pcim'),
                ('1-560780900', 'Amritsar Golden Polytechnic College', 'Engineering & Technology', 'Punjab', 'Amritsar', '143001', 'user_agpc'),
                ('1-901230450', 'Visakhapatnam Bayview Engineering Academy', 'Engineering & Technology', 'Andhra Pradesh', 'Visakhapatnam', '530003', 'user_vbea'),
                ('1-130460790', 'Gurugram Millennium Institute of AI & Data Sciences', 'Engineering & Technology', 'Haryana', 'Gurugram', '122002', 'user_gmai'),
                ('1-460790130', 'Coimbatore TexCity Institute of Mechanical Sciences', 'Engineering & Technology', 'Tamil Nadu', 'Coimbatore', '641014', 'user_ctim'),
                ('1-801240570', 'Nagpur Vidarbha Institute of Pharmacy & Research', 'Pharmacy', 'Maharashtra', 'Nagpur', '440010', 'user_nvip'),
            ]

            institutions_map = {}
            for aicte_id, name, itype, state, district, pincode, uname in INSTITUTION_DATA:
                inst, _ = Institution.objects.get_or_create(
                    aicte_id=aicte_id,
                    defaults={
                        'name': name,
                        'institution_type': itype,
                        'address': f"Institutional Area, Sector 5",
                        'state': state,
                        'district': district,
                        'pincode': pincode,
                        'status': InstitutionStatus.ACTIVE,
                        'contact_email': f"info@{uname}.edu.in",
                        'contact_phone': '+91-9876543210',
                    }
                )
                institutions_map[aicte_id] = inst

                # Create/update login user for institution
                iuser, _ = User.objects.get_or_create(
                    username=uname,
                    defaults={
                        'email': f"{uname}@edu.in",
                        'role': UserRole.INSTITUTION,
                        'institution': inst,
                        'first_name': name.split()[0],
                        'last_name': 'Registrar',
                        'designation': 'Registrar',
                    }
                )
                iuser.institution = inst
                iuser.set_password('College@2026Secure!')
                iuser.save()

            self.stdout.write(self.style.SUCCESS(f"Seeded {len(institutions_map)} Technical Institutions."))

            # Helper for adding field sources
            def seed_field_sources(instrument, claimed_dict, confirmed_dict=None):
                for fname, val in claimed_dict.items():
                    FieldSource.objects.get_or_create(
                        instrument=instrument,
                        field_name=fname,
                        value_source=DataProvenanceSource.INSTITUTION_SUBMITTED,
                        defaults={
                            'field_value': str(val),
                            'source_reference': f"Self-declaration {instrument.reference_number}",
                            'is_confirmed': False,
                        }
                    )
                if confirmed_dict:
                    for fname, val in confirmed_dict.items():
                        FieldSource.objects.get_or_create(
                            instrument=instrument,
                            field_name=fname,
                            value_source=DataProvenanceSource.BANK_CONFIRMED,
                            defaults={
                                'field_value': str(val),
                                'verified_by': officer_user,
                                'verified_at': timezone.now(),
                                'source_reference': 'CBS Live API Response Ref: CBS-ACK-7789',
                                'is_confirmed': True,
                            }
                        )

            # 3. Seed ~60 Demonstration Instruments covering all lifecycle scenarios
            today = get_effective_date()
            banks = [
                ('State Bank of India', 'SBIN0000691', 'Connaught Place Main Branch'),
                ('Punjab National Bank', 'PUNB0001200', 'Parliament Street Branch'),
                ('Canara Bank', 'CNRB0000101', 'MG Road Branch'),
                ('Bank of Baroda', 'BARB0BARODA', 'Alkapuri Corporate Branch'),
                ('Union Bank of India', 'UBIN0530018', 'Fort Mumbai Branch'),
            ]

            created_instruments_count = 0

            # -------------------------------------------------------------
            # Scenario A: New Submissions (SUBMITTED - Claimed only, unverified)
            # 8 Instruments
            # -------------------------------------------------------------
            for idx in range(1, 9):
                inst = list(institutions_map.values())[idx - 1]
                bank_name, ifsc, branch = banks[(idx - 1) % len(banks)]
                ref = f"FDR-NEW-2026-{idx:03d}"
                amount = 1500000.00 + (idx * 100000)
                ins, created = Instrument.objects.get_or_create(
                    reference_number=ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amount,
                        'issue_date': today - timedelta(days=20),
                        'maturity_date': today + timedelta(days=365 * 8),
                        'status': InstrumentStatus.SUBMITTED,
                        'trust_score': 35,
                        'lien_in_favour_of_aicte': True,
                        'joint_holder_name': f"{inst.name} and Member Secretary AICTE",
                        'created_by': admin_user,
                    }
                )
                seed_field_sources(ins, {'amount': amount, 'branch_ifsc': ifsc, 'issuing_bank': bank_name})
                created_instruments_count += 1

            # -------------------------------------------------------------
            # Scenario B: Tracking in Scrutiny (UNDER_SCRUTINY)
            # 8 Instruments
            # -------------------------------------------------------------
            for idx in range(1, 9):
                inst = list(institutions_map.values())[idx + 4]
                bank_name, ifsc, branch = banks[idx % len(banks)]
                ref = f"FDR-SCRUTINY-2026-{idx:03d}"
                amount = 2000000.00 + (idx * 50000)
                ins, created = Instrument.objects.get_or_create(
                    reference_number=ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amount,
                        'issue_date': today - timedelta(days=45),
                        'maturity_date': today + timedelta(days=365 * 7),
                        'status': InstrumentStatus.UNDER_SCRUTINY,
                        'trust_score': 65,
                        'lien_in_favour_of_aicte': True,
                        'joint_holder_name': f"{inst.name} & AICTE",
                        'ocr_extracted_data': {
                            'fdr_number': ref,
                            'amount': str(amount),
                            'bank': bank_name,
                            'ocr_confidence': 94.2
                        },
                        'created_by': officer_user,
                    }
                )
                seed_field_sources(ins, {'amount': amount, 'branch_ifsc': ifsc})
                Remark.objects.get_or_create(
                    instrument=ins,
                    author=officer_user,
                    role=UserRole.SCRUTINY_OFFICER,
                    remark_type='SCRUTINY_NOTE',
                    text=f"Verification initiated against {bank_name} CBS adapter. Awaiting confirmation."
                )
                created_instruments_count += 1

            # -------------------------------------------------------------
            # Scenario C: Approaching Maturity (EXPIRING - 7d, 30d, 60d, 90d buckets)
            # 10 Instruments with Reminders Generated
            # -------------------------------------------------------------
            offsets = [5, 14, 28, 45, 58, 72, 85, 88, 92, 100]
            for idx, days_left in enumerate(offsets, start=1):
                inst = list(institutions_map.values())[(idx + 2) % len(institutions_map)]
                bank_name, ifsc, branch = banks[idx % len(banks)]
                ref = f"FDR-EXPIRING-{days_left}D-{idx:03d}"
                mat_date = today + timedelta(days=days_left)
                amount = 2500000.00 + (idx * 150000)
                ins, created = Instrument.objects.get_or_create(
                    reference_number=ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amount,
                        'issue_date': mat_date - timedelta(days=365 * 8),
                        'maturity_date': mat_date,
                        'status': InstrumentStatus.EXPIRING,
                        'trust_score': 90,
                        'lien_in_favour_of_aicte': True,
                        'joint_holder_name': f"{inst.name} and AICTE",
                        'created_by': admin_user,
                    }
                )
                seed_field_sources(ins, {'amount': amount}, {'amount': amount})
                inst_user = User.objects.filter(institution=inst).first()
                Notification.objects.get_or_create(
                    dedup_key=f"seed:expiring:{ins.id}:{days_left}",
                    defaults={
                        'instrument': ins,
                        'recipient': inst_user,
                        'recipient_role': UserRole.INSTITUTION,
                        'recipient_email': inst.contact_email,
                        'title': f"Urgent: Security Deposit {ref} Expiring in {days_left} Days",
                        'message': f"Contractual maturity date is {mat_date}. Immediate renewal or replacement required per AICTE regulations.",
                        'channel': NotificationChannel.EMAIL,
                        'notification_type': NotificationType.REMINDER,
                        'offset_days': days_left,
                        'is_read': False,
                        'sent_at': timezone.now() - timedelta(days=1),
                    }
                )
                created_instruments_count += 1

            # -------------------------------------------------------------
            # Scenario D: Verified & Active (ACTIVE & VERIFIED - High trust score, CBS confirmed)
            # 12 Instruments
            # -------------------------------------------------------------
            for idx in range(1, 13):
                inst = list(institutions_map.values())[(idx + 7) % len(institutions_map)]
                bank_name, ifsc, branch = banks[idx % len(banks)]
                ref = f"FDR-ACTIVE-VERIFIED-{idx:03d}"
                amount = 3000000.00 + (idx * 200000)
                stat = InstrumentStatus.ACTIVE if idx % 2 == 0 else InstrumentStatus.VERIFIED
                ins, created = Instrument.objects.get_or_create(
                    reference_number=ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amount,
                        'issue_date': today - timedelta(days=200),
                        'maturity_date': today + timedelta(days=365 * 6),
                        'status': stat,
                        'trust_score': 98,
                        'lien_in_favour_of_aicte': True,
                        'joint_holder_name': f"{inst.name} & Member Secretary AICTE",
                        'created_by': officer_user,
                    }
                )
                seed_field_sources(
                    ins,
                    {'amount': amount, 'branch_ifsc': ifsc, 'issuing_bank': bank_name},
                    {'amount': amount, 'branch_ifsc': ifsc, 'issuing_bank': bank_name}
                )
                created_instruments_count += 1

            # -------------------------------------------------------------
            # Scenario E: Renewal & Replacement Chains (REPLACED -> New ACTIVE)
            # 8 Instruments (4 linked pairs)
            # -------------------------------------------------------------
            for idx in range(1, 5):
                inst = list(institutions_map.values())[(idx + 12) % len(institutions_map)]
                bank_name, ifsc, branch = banks[idx % len(banks)]
                old_ref = f"FDR-OLD-LAPSED-2021-{idx:03d}"
                new_ref = f"FDR-REPLACEMENT-2026-{idx:03d}"
                amount = 2000000.00

                new_ins, _ = Instrument.objects.get_or_create(
                    reference_number=new_ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amount,
                        'issue_date': today - timedelta(days=10),
                        'maturity_date': today + timedelta(days=365 * 8),
                        'status': InstrumentStatus.ACTIVE,
                        'trust_score': 95,
                        'lien_in_favour_of_aicte': True,
                        'joint_holder_name': f"{inst.name} and AICTE",
                    }
                )
                seed_field_sources(new_ins, {'amount': amount}, {'amount': amount})

                old_ins, _ = Instrument.objects.get_or_create(
                    reference_number=old_ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amount,
                        'issue_date': today - timedelta(days=365 * 8),
                        'maturity_date': today - timedelta(days=15),
                        'status': InstrumentStatus.REPLACED,
                        'trust_score': 90,
                        'lien_in_favour_of_aicte': True,
                    }
                )
                new_ins.replaces = old_ins
                new_ins.save(update_fields=['replaces'])

                created_instruments_count += 2

            # -------------------------------------------------------------
            # Scenario F: Open Discrepancies (DISCREPANCY - Amount/Lien/Holder Mismatch)
            # 6 Instruments
            # -------------------------------------------------------------
            discrepancy_scenarios = [
                ('AMOUNT_MISMATCH_BANK', DiscrepancySeverity.CRITICAL, "Amount Discrepancy: Ledger balance mismatch", "Claimed ₹25,00,000 but CBS ledger indicates balance of ₹15,00,000 only.", 2500000.00),
                ('LIEN_NOT_CONFIRMED', DiscrepancySeverity.CRITICAL, "Lien Missing: AICTE Lien not recorded in CBS", "Bank confirmation states FDR is clean without official lien marked to AICTE.", 1800000.00),
                ('JOINT_NAME_MISMATCH', DiscrepancySeverity.HIGH, "Account Holder Mismatch", "Account holder name reflects private society instead of recognized Institute.", 2200000.00),
                ('MATURITY_DATE_MISMATCH', DiscrepancySeverity.MEDIUM, "Contractual Maturity Mismatch", "Contractual maturity date in CBS is 2028-01-01 instead of claimed 2034-01-01.", 1500000.00),
                ('BRANCH_IFSC_MISMATCH', DiscrepancySeverity.LOW, "Branch Code Variance", "IFSC corresponds to sub-branch; confirmation needed for master record.", 3000000.00),
                ('LEGAL_DISPUTE_HOLD', DiscrepancySeverity.HIGH, "Judicial Freeze Flag", "Bank letter indicates ongoing judicial freeze under local civil dispute.", 2000000.00),
            ]
            for idx, (rcode, dsev, dtitle, ddesc, amt) in enumerate(discrepancy_scenarios, start=1):
                inst = list(institutions_map.values())[(idx + 15) % len(institutions_map)]
                bank_name, ifsc, branch = banks[idx % len(banks)]
                ref = f"FDR-FLAGGED-DISC-{idx:03d}"
                ins, _ = Instrument.objects.get_or_create(
                    reference_number=ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amt,
                        'issue_date': today - timedelta(days=90),
                        'maturity_date': today + timedelta(days=365 * 5),
                        'status': InstrumentStatus.DISCREPANCY,
                        'trust_score': 20,
                        'lien_in_favour_of_aicte': False,
                        'compliance_hold': True,
                        'compliance_hold_reason': ddesc,
                    }
                )
                seed_field_sources(ins, {'amount': amt, 'branch_ifsc': ifsc})
                Discrepancy.objects.get_or_create(
                    instrument=ins,
                    rule_code=rcode,
                    defaults={
                        'severity': dsev,
                        'title': dtitle,
                        'description': ddesc,
                        'details': {'field': 'amount' if 'amount' in ddesc.lower() else 'lien_in_favour_of_aicte', 'claimed': str(amt)},
                        'is_resolved': False,
                    }
                )
                created_instruments_count += 1

            # -------------------------------------------------------------
            # Scenario G: Release in Progress (RELEASE_REQUESTED)
            # 4 Instruments (All preconditions satisfied, awaiting approval)
            # -------------------------------------------------------------
            for idx in range(1, 5):
                inst = list(institutions_map.values())[(idx + 18) % len(institutions_map)]
                bank_name, ifsc, branch = banks[idx % len(banks)]
                ref = f"FDR-RELEASE-PENDING-{idx:03d}"
                amount = 2500000.00
                ins, _ = Instrument.objects.get_or_create(
                    reference_number=ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amount,
                        'issue_date': today - timedelta(days=365 * 8),
                        'maturity_date': today - timedelta(days=30),
                        'status': InstrumentStatus.RELEASE_REQUESTED,
                        'trust_score': 98,
                        'lien_in_favour_of_aicte': True,
                    }
                )
                seed_field_sources(ins, {'amount': amount}, {'amount': amount})
                Remark.objects.get_or_create(
                    instrument=ins,
                    author=officer_user,
                    role=UserRole.SCRUTINY_OFFICER,
                    remark_type='SCRUTINY_NOTE',
                    text="Preconditions checked: Bank confirmed, no open discrepancies, checklist 4/4 passed. Recommended for release."
                )
                created_instruments_count += 1

            # -------------------------------------------------------------
            # Scenario H: Formally Released (RELEASED - Refunded per Sanction Order)
            # 4 Instruments
            # -------------------------------------------------------------
            for idx in range(1, 5):
                inst = list(institutions_map.values())[(idx + 20) % len(institutions_map)]
                bank_name, ifsc, branch = banks[idx % len(banks)]
                ref = f"FDR-RELEASED-REFUNDED-{idx:03d}"
                amount = 3500000.00
                ins, _ = Instrument.objects.get_or_create(
                    reference_number=ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amount,
                        'issue_date': today - timedelta(days=365 * 10),
                        'maturity_date': today - timedelta(days=90),
                        'status': InstrumentStatus.RELEASED,
                        'trust_score': 100,
                        'lien_in_favour_of_aicte': False,
                    }
                )
                seed_field_sources(ins, {'amount': amount}, {'amount': amount})
                Remark.objects.get_or_create(
                    instrument=ins,
                    author=approver_user,
                    role=UserRole.APPROVING_AUTHORITY,
                    remark_type='APPROVAL_NOTE',
                    text=f"Sanctioned for release per Order Ref: AICTE/FD/REL/2026/00{idx}. Bank instructed to discharge lien."
                )
                created_instruments_count += 1

            # -------------------------------------------------------------
            # Scenario I: Matured & Overdue (MATURED - Escalation ladder active)
            # 3 Instruments
            # -------------------------------------------------------------
            for idx in range(1, 4):
                inst = list(institutions_map.values())[(idx + 21) % len(institutions_map)]
                bank_name, ifsc, branch = banks[idx % len(banks)]
                ref = f"FDR-MATURED-OVERDUE-{idx:03d}"
                amount = 1800000.00
                ins, _ = Instrument.objects.get_or_create(
                    reference_number=ref,
                    defaults={
                        'institution': inst,
                        'instrument_type': InstrumentType.FDR,
                        'issuing_bank': bank_name,
                        'issuing_branch': branch,
                        'branch_ifsc': ifsc,
                        'amount': amount,
                        'issue_date': today - timedelta(days=365 * 8),
                        'maturity_date': today - timedelta(days=60),
                        'status': InstrumentStatus.MATURED,
                        'trust_score': 50,
                        'lien_in_favour_of_aicte': True,
                    }
                )
                seed_field_sources(ins, {'amount': amount}, {'amount': amount})
                created_instruments_count += 1

            # 4. Standard Reminder and Escalation Rules
            offsets = [90, 60, 30, 7]
            for offset in offsets:
                ReminderRule.objects.get_or_create(
                    offset_days=offset,
                    defaults={
                        'name': f"Standard {offset}-Day Renewal Notice",
                        'channel': NotificationChannel.ALL,
                        'target_role': 'INSTITUTION',
                        'template_subject': f"Notice: FDR Maturing in {offset} Days",
                        'template_body': f"Security deposit / FDR #{{reference_number}} is maturing in {offset} calendar days. Please initiate renewal or submit release documentation.",
                        'is_active': True,
                    }
                )

            escalation_ladder = [
                ('14-Day Overdue Institution Notice', 14, 'INSTITUTION', 'SCRUTINY_OFFICER'),
                ('30-Day Overdue Scrutiny Officer Escalation', 30, 'SCRUTINY_OFFICER', 'APPROVING_AUTHORITY'),
                ('60-Day Overdue Senior Approver Escalation', 60, 'APPROVING_AUTHORITY', 'DIRECTOR'),
                ('90-Day Overdue Director Enforcement Escalation', 90, 'DIRECTOR', 'ADMIN'),
            ]
            for name, days, f_lvl, t_lvl in escalation_ladder:
                EscalationRule.objects.get_or_create(
                    wait_period_days=days,
                    from_level=f_lvl,
                    to_level=t_lvl,
                    defaults={
                        'name': name,
                        'trigger_condition': EscalationCondition.OVERDUE_MATURED,
                        'channel': NotificationChannel.IN_APP,
                        'template_subject': f"ESCALATION LEVEL {t_lvl}: FDR #{{reference_number}} Compliance Overdue",
                        'template_body': f"Case escalated to {t_lvl}: Instrument #{{reference_number}} has remained unresolved for {days} days past maturity.",
                        'is_active': True,
                    }
                )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded {len(institutions_map)} Technical Institutions and {created_instruments_count} Instruments covering all 9 lifecycle scenarios."
        ))
