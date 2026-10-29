export type DataProvenance = 'INSTITUTION_SUBMITTED' | 'OFFICER_ENTERED' | 'BANK_CONFIRMED';

export type UserRole = 'INSTITUTION' | 'SCRUTINY_OFFICER' | 'APPROVING_AUTHORITY' | 'ADMIN';

export type InstrumentStatus =
  | 'Submitted'
  | 'Under Scrutiny'
  | 'Verified'
  | 'Active'
  | 'Expiring'
  | 'Matured'
  | 'Renewed'
  | 'Replaced'
  | 'Release Requested'
  | 'Released'
  | 'Discrepancy'
  | 'Rejected';

export interface DocumentItem {
  id: number;
  instrument: number;
  document_type: string;
  file_name: string;
  mime_type: string;
  sha256_hash: string;
  file_size_bytes: number;
  version: number;
  is_current_version: boolean;
  is_encrypted: boolean;
  is_duplicate_hash: boolean;
  duplicate_of: number | null;
  duplicate_of_reference?: string | null;
  uploaded_by_username?: string;
  uploaded_at: string;
  download_url: string;
}

export interface FieldSourceItem {
  id: number;
  field_name: string;
  field_value: string;
  value_source: DataProvenance;
  verified_at: string | null;
  verified_by_username: string | null;
  source_reference: string;
  is_confirmed: boolean;
  created_at: string;
}

export interface RemarkItem {
  id: number;
  instrument: number;
  author_username: string;
  role: string;
  remark_type: string;
  text: string;
  is_internal: boolean;
  created_at: string;
}

export interface DiscrepancyItem {
  id: number;
  instrument: number;
  rule_code: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  description: string;
  details: Record<string, any>;
  is_resolved: boolean;
  resolved_by?: number | null;
  resolved_by_username?: string | null;
  resolved_at?: string | null;
  resolution_note?: string;
  created_at: string;
}

export interface TimelineNode {
  id: number;
  reference_number: string;
  issuing_bank: string;
  amount: string;
  status: InstrumentStatus;
  issue_date: string | null;
  maturity_date: string | null;
  is_current: boolean;
  replaces_id: number | null;
  renewal_type?: string | null;
  generation?: number;
  created_at: string | null;
}

export interface ReleaseChecklist {
  is_bank_confirmed: boolean;
  no_open_discrepancies: boolean;
  open_discrepancies_count: number;
  lock_in_satisfied: boolean;
  has_noc_document: boolean;
  is_matured: boolean;
  no_compliance_hold: boolean;
  compliance_hold_reason: string;
  mandatory_documents_present: boolean;
  has_required_documents?: boolean;
  can_approve: boolean;
  all_conditions_met?: boolean;
  blocking_reasons: string[];
}

export interface InstrumentItem {
  id: number;
  institution: number;
  institution_name: string;
  institution_aicte_id: string;
  institution_type?: string;
  instrument_type: string;
  reference_number: string;
  issuing_bank: string;
  issuing_branch: string;
  branch_ifsc: string;
  amount: string;
  issue_date: string;
  maturity_date: string;
  lien_in_favour_of_aicte: boolean;
  joint_holder_name: string;
  status: InstrumentStatus;
  trust_score: number;
  ocr_extracted_data?: Record<string, any>;
  replaces?: number | null;
  replaces_reference?: string | null;
  renewal_type?: string;
  replacement_chain?: TimelineNode[];
  release_checklist?: ReleaseChecklist;
  release_requested_at?: string | null;
  release_justification?: string;
  scrutiny_recommended_at?: string | null;
  scrutiny_recommendation?: string;
  scrutiny_notes?: string;
  released_at?: string | null;
  released_by?: number | null;
  released_by_username?: string | null;
  release_order_reference?: string;
  rejection_reason?: string;
  compliance_hold?: boolean;
  compliance_hold_reason?: string;
  field_sources: FieldSourceItem[];
  documents: DocumentItem[];
  discrepancies: DiscrepancyItem[];
  remarks: RemarkItem[];
  claimed_vs_confirmed: Record<string, { claimed: any; confirmed: any }>;
  created_at: string;
  updated_at: string;
}

export interface HealthCheckResponse {
  status: string;
  timestamp: string;
  service: string;
  version: string;
  checks: {
    database: boolean;
    redis: boolean;
    database_error?: string;
    redis_error?: string;
  };
  bank_verification_adapter: {
    name: string;
    is_mock: boolean;
    class: string;
    error?: string;
  };
}

export interface NotificationItem {
  id: number;
  instrument: number | null;
  instrument_reference?: string;
  institution_name?: string;
  recipient: number | null;
  recipient_role: string;
  recipient_email?: string;
  recipient_phone?: string;
  channel: 'IN_APP' | 'EMAIL' | 'SMS' | 'ALL';
  notification_type: 'REMINDER' | 'ESCALATION' | 'STATUS_CHANGE' | 'OVERDUE';
  title: string;
  message: string;
  offset_days?: number | null;
  escalation_level?: string;
  is_read: boolean;
  sent_at: string;
  read_at?: string | null;
}

export interface ReminderRuleItem {
  id: number;
  name: string;
  offset_days: number;
  channel: string;
  target_role: string;
  template_subject: string;
  template_body: string;
  is_active: boolean;
}

export interface EscalationRuleItem {
  id: number;
  name: string;
  trigger_condition: string;
  wait_period_days: number;
  from_level: string;
  to_level: string;
  channel: string;
  template_subject: string;
  template_body: string;
  is_active: boolean;
}

export interface EscalationRecordItem {
  id: number;
  instrument: number;
  instrument_reference?: string;
  institution_name?: string;
  trigger_condition: string;
  from_level: string;
  to_level: string;
  reason: string;
  triggered_at: string;
  is_resolved: boolean;
}

export interface SimulatedDateInfo {
  is_simulation_allowed: boolean;
  is_active: boolean;
  simulated_date: string | null;
  effective_date: string;
  real_today: string;
  environment: string;
}

export interface RiskWorklistItem {
  id: number;
  reference_number: string;
  institution_id: number;
  institution_name: string;
  institution_aicte_id: string;
  issuing_bank: string;
  amount: string;
  status: InstrumentStatus;
  issue_date: string | null;
  maturity_date: string | null;
  days_to_maturity: number | null;
  risk_score: number;
  risk_tier: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  risk_factors: string[];
  open_discrepancies_count: number;
  compliance_hold: boolean;
}

export interface ExpiryMonthForecast {
  month_label: string;
  month_key: string;
  count: number;
  total_amount: number;
}

export interface OfficerDashboardData {
  effective_date: string;
  counts: {
    total_instruments: number;
    active: number;
    expiring_30: number;
    expiring_60: number;
    expiring_90: number;
    expiring_total: number;
    matured: number;
    renewed: number;
    released: number;
    replaced: number;
    pending_verification: number;
    discrepancies: number;
    total_amount: number;
    active_amount: number;
  };
  expiry_buckets: {
    '0_30_days': number;
    '31_60_days': number;
    '61_90_days': number;
    total_expiring: number;
  };
  status_distribution: Array<{ status: string; label: string; count: number }>;
  bank_distribution: Array<{ bank: string; count: number; total_amount: number }>;
  expiry_timeline: ExpiryMonthForecast[];
  risk_worklist: RiskWorklistItem[];
}

export interface InstitutionDeadlineItem {
  id: number;
  reference_number: string;
  issuing_bank: string;
  amount: string;
  status: InstrumentStatus;
  issue_date: string | null;
  maturity_date: string | null;
  days_left: number;
  urgency: 'OVERDUE' | 'CRITICAL' | 'HIGH' | 'MEDIUM';
  action_required: string;
  has_discrepancies: boolean;
}

export interface InstitutionDashboardData {
  effective_date: string;
  institution_id: number;
  summary: {
    total_instruments: number;
    total_amount: number;
    active_count: number;
    expiring_count: number;
    matured_count: number;
    under_scrutiny_count: number;
    discrepancy_count: number;
    released_count: number;
    replaced_count: number;
  };
  upcoming_deadlines: InstitutionDeadlineItem[];
}

export interface SavedFilterItem {
  id: number;
  name: string;
  filter_params: Record<string, any>;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuditEntryItem {
  id: number;
  actor_username: string;
  role: string;
  action: string;
  object_type: string;
  object_id: string;
  object_repr: string;
  before_values: Record<string, any>;
  after_values: Record<string, any>;
  ip_address: string | null;
  user_agent: string;
  timestamp: string;
  previous_hash: string;
  entry_hash: string;
}

export interface VerifyChainResponse {
  valid: boolean;
  total_verified: number;
  latest_hash?: string;
  first_broken_id?: number | null;
  reason?: string;
  message?: string;
}

export interface TotpSetupResponse {
  totp_enabled: boolean;
  secret: string;
  otpauth_uri: string;
  username: string;
}

export interface ImpactMetricsResponse {
  generated_at: string;
  effective_date: string;
  summary: {
    total_instruments_managed: number;
    avg_verification_turnaround_days: number;
    manual_steps_avoided: number;
    renewals_caught_before_expiry: number;
    record_accuracy_pct: number;
    confirmed_instruments_share_pct: number;
    turnaround_reduction_pct: number;
  };
  breakdown: {
    automated_reminders_dispatched: number;
    auto_discrepancy_flags_detected: number;
    ocr_certificates_extracted: number;
    bank_cbs_queries_executed: number;
    proactive_expiries_in_flight: number;
    renewals_successfully_chained: number;
  };
  pending_cases: {
    total_pending: number;
    under_scrutiny: number;
    open_discrepancies: number;
    pending_approval: number;
    matured_unresolved: number;
  };
  baseline_comparison: {
    assumptions_label: string;
    benchmark_date: string;
    metrics: Array<{
      key: string;
      label: string;
      legacy_manual: string;
      digital_portal: string;
      improvement: string;
      favorable: boolean;
      description: string;
    }>;
  };
}




