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
