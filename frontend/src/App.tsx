import React, { useEffect, useState, useRef } from 'react';
import {
  InstrumentItem,
  DocumentItem,
  DiscrepancyItem,
  HealthCheckResponse,
  NotificationItem,
  ReminderRuleItem,
  EscalationRuleItem,
  SimulatedDateInfo,
  OfficerDashboardData,
  InstitutionDashboardData,
  SavedFilterItem,
} from './types/provenance';

const USERS = [
  { username: 'user_ditm', label: 'Delhi Institute (Institution)', password: 'College@DITM2026', role: 'INSTITUTION' },
  { username: 'user_mumbai', label: 'Mumbai College (Institution)', password: 'College@Mumbai2026', role: 'INSTITUTION' },
  { username: 'officer_sharma', label: 'Rajesh Sharma (Scrutiny Officer)', password: 'Officer@AICTE2026', role: 'SCRUTINY_OFFICER' },
  { username: 'approver_verma', label: 'Vikram Verma (Approving Authority)', password: 'Approver@AICTE2026', role: 'APPROVING_AUTHORITY' },
  { username: 'aicte_admin', label: 'Regulation Bureau Admin', password: 'Admin@AICTE2026', role: 'ADMIN' },
];

export const App: React.FC = () => {
  const [currentUserIdx, setCurrentUserIdx] = useState<number>(0);
  const [authToken, setAuthToken] = useState<string>('');
  const [userProfile, setUserProfile] = useState<any>(null);
  const [instruments, setInstruments] = useState<InstrumentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // Modals & Navigation
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState<boolean>(false);
  const [selectedInstrument, setSelectedInstrument] = useState<InstrumentItem | null>(null);
  const [modalTab, setModalTab] = useState<'overview' | 'discrepancies' | 'documents' | 'remarks' | 'lineage' | 'release'>('overview');

  // Phase 4: Simulated Date & Monitoring Job State
  const [simulatedDateInfo, setSimulatedDateInfo] = useState<SimulatedDateInfo | null>(null);
  const [customSimDateInput, setCustomSimDateInput] = useState<string>('2028-06-01');
  const [isRunningMonitoringJob, setIsRunningMonitoringJob] = useState<boolean>(false);
  const [monitoringJobResult, setMonitoringJobResult] = useState<any | null>(null);

  // Phase 4: Notifications State
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadNotifCount, setUnreadNotifCount] = useState<number>(0);
  const [isNotifModalOpen, setIsNotifModalOpen] = useState<boolean>(false);
  const [notifTab, setNotifTab] = useState<'all' | 'unread'>('all');

  // Phase 4: Rules & Policy Modal State
  const [isRulesModalOpen, setIsRulesModalOpen] = useState<boolean>(false);
  const [rulesTab, setRulesTab] = useState<'reminders' | 'escalations'>('reminders');
  const [reminderRules, setReminderRules] = useState<ReminderRuleItem[]>([]);
  const [escalationRules, setEscalationRules] = useState<EscalationRuleItem[]>([]);

  // Form State for Submit FDR
  const [refNumber, setRefNumber] = useState<string>('');
  const [bankName, setBankName] = useState<string>('State Bank of India');
  const [branchName, setBranchName] = useState<string>('');
  const [ifsc, setIfsc] = useState<string>('');
  const [amount, setAmount] = useState<string>('');
  const [issueDate, setIssueDate] = useState<string>('2024-01-01');
  const [maturityDate, setMaturityDate] = useState<string>('2032-01-01');
  const [lienMarked, setLienMarked] = useState<boolean>(true);
  const [jointHolder, setJointHolder] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileHashPreview, setFileHashPreview] = useState<string>('');
  const [submitError, setSubmitError] = useState<string>('');
  const [submitSuccess, setSubmitSuccess] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Phase 3: OCR Extractor State
  const [ocrLoading, setOcrLoading] = useState<boolean>(false);
  const [ocrExtractedData, setOcrExtractedData] = useState<any | null>(null);
  const [ocrError, setOcrError] = useState<string>('');

  // Phase 3: Verification & Scrutiny State
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifyNotes, setVerifyNotes] = useState<string>('Verified via CBS Mock Bank Adapter');
  const [lastBankResult, setLastBankResult] = useState<any | null>(null);

  // Phase 3: Resolve Discrepancy Modal
  const [resolvingDiscrepancy, setResolvingDiscrepancy] = useState<DiscrepancyItem | null>(null);
  const [resolutionNote, setResolutionNote] = useState<string>('');
  const [isResolving, setIsResolving] = useState<boolean>(false);

  // Phase 3: Flag Discrepancy Modal
  const [isFlagModalOpen, setIsFlagModalOpen] = useState<boolean>(false);
  const [flagReason, setFlagReason] = useState<string>('');
  const [flagFieldName, setFlagFieldName] = useState<string>('');
  const [flagSeverity, setFlagSeverity] = useState<'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'>('HIGH');
  const [isFlagging, setIsFlagging] = useState<boolean>(false);

  // New Version Upload State in Detail Modal
  const [versionDocType, setVersionDocType] = useState<string>('FDR_CERTIFICATE');
  const [versionFile, setVersionFile] = useState<File | null>(null);
  const [uploadingVersion, setUploadingVersion] = useState<boolean>(false);
  const [versionUploadError, setVersionUploadError] = useState<string>('');

  // Remark State
  const [newRemarkText, setNewRemarkText] = useState<string>('');
  const [newRemarkType, setNewRemarkType] = useState<string>('SCRUTINY_NOTE');
  const [isSubmittingRemark, setIsSubmittingRemark] = useState<boolean>(false);

  // Phase 5: Renewal / Replacement State
  const [replacesId, setReplacesId] = useState<string>('');
  const [renewalType, setRenewalType] = useState<string>('REPLACEMENT');

  // Phase 5: Release & Refund State
  const [releaseJustification, setReleaseJustification] = useState<string>('');
  const [isRequestingRelease, setIsRequestingRelease] = useState<boolean>(false);
  const [scrutinyRecommendation, setScrutinyRecommendation] = useState<'RECOMMEND_RELEASE' | 'FLAG_FOR_AUDIT'>('RECOMMEND_RELEASE');
  const [scrutinyNotes, setScrutinyNotes] = useState<string>('Preconditions verified; recommend release.');
  const [isScrutinizing, setIsScrutinizing] = useState<boolean>(false);
  const [sanctionOrderRef, setSanctionOrderRef] = useState<string>('');
  const [sanctionNotes, setSanctionNotes] = useState<string>('Sanctioned per AICTE Deposit Regulations.');
  const [isSanctioning, setIsSanctioning] = useState<boolean>(false);
  const [rejectionReasonInput, setRejectionReasonInput] = useState<string>('');
  const [isRejecting, setIsRejecting] = useState<boolean>(false);
  const [holdReason, setHoldReason] = useState<string>('');
  const [isTogglingHold, setIsTogglingHold] = useState<boolean>(false);
  const [releaseActionSuccess, setReleaseActionSuccess] = useState<string>('');
  const [releaseActionError, setReleaseActionError] = useState<string>('');

  // Phase 6: Dashboards & Analytics State
  const [officerDashboard, setOfficerDashboard] = useState<OfficerDashboardData | null>(null);
  const [institutionDashboard, setInstitutionDashboard] = useState<InstitutionDashboardData | null>(null);
  const [loadingDashboard, setLoadingDashboard] = useState<boolean>(false);
  const [officerTab, setOfficerTab] = useState<'kpi' | 'timeline' | 'risk'>('kpi');

  // Phase 6: Advanced Filters & Saved Filters
  const [filterBank, setFilterBank] = useState<string>('');
  const [filterMinAmount, setFilterMinAmount] = useState<string>('');
  const [filterMaxAmount, setFilterMaxAmount] = useState<string>('');
  const [filterMaturityFrom, setFilterMaturityFrom] = useState<string>('');
  const [filterMaturityTo, setFilterMaturityTo] = useState<string>('');
  const [filterDiscrepancyType, setFilterDiscrepancyType] = useState<string>('');
  const [savedFilters, setSavedFilters] = useState<SavedFilterItem[]>([]);
  const [activeSavedFilterId, setActiveSavedFilterId] = useState<number | null>(null);
  const [isSaveFilterModalOpen, setIsSaveFilterModalOpen] = useState<boolean>(false);
  const [saveFilterNameInput, setSaveFilterNameInput] = useState<string>('');
  const [isSavingFilter, setIsSavingFilter] = useState<boolean>(false);

  // Phase 6: Reports & Exports Modal
  const [isReportsModalOpen, setIsReportsModalOpen] = useState<boolean>(false);
  const [downloadingReportKey, setDownloadingReportKey] = useState<string | null>(null);
  const [isSendingWeeklySummary, setIsSendingWeeklySummary] = useState<boolean>(false);
  const [weeklySummaryMsg, setWeeklySummaryMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const ocrFileInputRef = useRef<HTMLInputElement>(null);

  // 1. Authenticate & Fetch Token
  const loginUser = async (userObj: typeof USERS[0]) => {
    setLoading(true);
    try {
      const res = await fetch('/api/auth/token/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: userObj.username, password: userObj.password }),
      });
      if (res.ok) {
        const data = await res.json();
        setAuthToken(data.access);
        setUserProfile(data.user);
        fetchInstruments(data.access);
        fetchNotifications(data.access);
        fetchSavedFilters(data.access);
        if (userObj.role === 'INSTITUTION') {
          fetchInstitutionDashboard(data.access);
          setOfficerDashboard(null);
        } else {
          fetchOfficerDashboard(data.access);
          setInstitutionDashboard(null);
        }
        if (userObj.role === 'ADMIN') {
          fetchSimulatedDateInfo(data.access);
          fetchRules(data.access);
        }
      }
    } catch (err) {
      console.error('Login failed:', err);
    } finally {
      setLoading(false);
    }
  };

  // 2. Fetch Instruments
  const fetchInstruments = async (token: string) => {
    try {
      const res = await fetch('/api/instruments/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const list = data.results || data;
        const arrayList = Array.isArray(list) ? list : [];
        setInstruments(arrayList);
        if (selectedInstrument) {
          const updated = arrayList.find((i: InstrumentItem) => i.id === selectedInstrument.id);
          if (updated) setSelectedInstrument(updated);
        }
      }
    } catch (err) {
      console.error('Fetch instruments error:', err);
    }
  };

  // 3. Refresh single instrument
  const refreshSingleInstrument = async (instId: number) => {
    try {
      const res = await fetch(`/api/instruments/${instId}/`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedInstrument(updated);
      }
    } catch (err) {
      console.error('Error refreshing instrument:', err);
    }
  };

  // 4. Notifications
  const fetchNotifications = async (token: string) => {
    try {
      const res = await fetch('/api/notifications/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const list = data.results || data;
        setNotifications(Array.isArray(list) ? list : []);
      }
      const countRes = await fetch('/api/notifications/unread-count/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (countRes.ok) {
        const cData = await countRes.json();
        setUnreadNotifCount(cData.unread_count || 0);
      }
    } catch (err) {
      console.error('Notifications fetch error:', err);
    }
  };

  const handleMarkNotifRead = async (id: number) => {
    try {
      const res = await fetch(`/api/notifications/${id}/mark-read/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        fetchNotifications(authToken);
      }
    } catch (err) {
      console.error('Mark read error:', err);
    }
  };

  const handleMarkAllNotifsRead = async () => {
    try {
      const res = await fetch('/api/notifications/mark-all-read/', {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        fetchNotifications(authToken);
      }
    } catch (err) {
      console.error('Mark all read error:', err);
    }
  };

  // 5. Phase 4: Simulated Date & Time-Travel Controls
  const fetchSimulatedDateInfo = async (token: string) => {
    try {
      const res = await fetch('/api/admin/simulated-date/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSimulatedDateInfo(data);
        if (data.simulated_date) {
          setCustomSimDateInput(data.simulated_date);
        }
      }
    } catch (err) {
      console.error('Simulated date info error:', err);
    }
  };

  const handleSetSimulatedDate = async (targetDateStr: string | null) => {
    try {
      const res = await fetch('/api/admin/simulated-date/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ simulated_date: targetDateStr }),
      });
      if (res.ok) {
        const data = await res.json();
        setSimulatedDateInfo(data);
        fetchInstruments(authToken);
        if (USERS[currentUserIdx].role === 'INSTITUTION') {
          fetchInstitutionDashboard(authToken);
        } else {
          fetchOfficerDashboard(authToken);
        }
      } else {
        const err = await res.json();
        alert(`Failed to set simulated date: ${JSON.stringify(err)}`);
      }
    } catch (err) {
      console.error('Set simulated date error:', err);
    }
  };

  const handleRunMonitoringJob = async () => {
    setIsRunningMonitoringJob(true);
    setMonitoringJobResult(null);
    try {
      const res = await fetch('/api/admin/run-monitoring-job/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ effective_date: simulatedDateInfo?.effective_date }),
      });
      if (res.ok) {
        const result = await res.json();
        setMonitoringJobResult(result);
        fetchInstruments(authToken);
        fetchNotifications(authToken);
        if (USERS[currentUserIdx].role === 'INSTITUTION') {
          fetchInstitutionDashboard(authToken);
        } else {
          fetchOfficerDashboard(authToken);
        }
      } else {
        const err = await res.json();
        alert(`Monitoring job failed: ${JSON.stringify(err)}`);
      }
    } catch (err) {
      console.error('Monitoring job trigger error:', err);
    } finally {
      setIsRunningMonitoringJob(false);
    }
  };

  // 6. Phase 4: Rules Management
  const fetchRules = async (token: string) => {
    try {
      const [remRes, escRes] = await Promise.all([
        fetch('/api/reminder-rules/', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/escalation-rules/', { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (remRes.ok) {
        const remData = await remRes.json();
        setReminderRules(Array.isArray(remData.results || remData) ? remData.results || remData : []);
      }
      if (escRes.ok) {
        const escData = await escRes.json();
        setEscalationRules(Array.isArray(escData.results || escData) ? escData.results || escData : []);
      }
    } catch (err) {
      console.error('Rules fetch error:', err);
    }
  };

  const handleToggleReminderRule = async (rule: ReminderRuleItem) => {
    try {
      const res = await fetch(`/api/reminder-rules/${rule.id}/`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ is_active: !rule.is_active }),
      });
      if (res.ok) {
        fetchRules(authToken);
      }
    } catch (err) {
      console.error('Toggle reminder error:', err);
    }
  };

  const handleToggleEscalationRule = async (rule: EscalationRuleItem) => {
    try {
      const res = await fetch(`/api/escalation-rules/${rule.id}/`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ is_active: !rule.is_active }),
      });
      if (res.ok) {
        fetchRules(authToken);
      }
    } catch (err) {
      console.error('Toggle escalation error:', err);
    }
  };

  // 7. Phase 6: Dashboards & Analytics
  const fetchOfficerDashboard = async (token: string) => {
    setLoadingDashboard(true);
    try {
      const res = await fetch('/api/reports/officer-dashboard/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data: OfficerDashboardData = await res.json();
        setOfficerDashboard(data);
      }
    } catch (err) {
      console.error('Officer dashboard fetch error:', err);
    } finally {
      setLoadingDashboard(false);
    }
  };

  const fetchInstitutionDashboard = async (token: string) => {
    setLoadingDashboard(true);
    try {
      const res = await fetch('/api/reports/institution-dashboard/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data: InstitutionDashboardData = await res.json();
        setInstitutionDashboard(data);
      }
    } catch (err) {
      console.error('Institution dashboard fetch error:', err);
    } finally {
      setLoadingDashboard(false);
    }
  };

  // 8. Phase 6: Saved Filters
  const fetchSavedFilters = async (token: string) => {
    try {
      const res = await fetch('/api/saved-filters/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const list = Array.isArray(data) ? data : data.results || [];
        setSavedFilters(list);
      }
    } catch (err) {
      console.error('Saved filters fetch error:', err);
    }
  };

  const handleSaveFilter = async () => {
    if (!saveFilterNameInput.trim()) return;
    setIsSavingFilter(true);
    try {
      const payload = {
        name: saveFilterNameInput.trim(),
        filter_params: {
          search: searchQuery,
          status: statusFilter,
          bank: filterBank,
          min_amount: filterMinAmount,
          max_amount: filterMaxAmount,
          maturity_from: filterMaturityFrom,
          maturity_to: filterMaturityTo,
          discrepancy_type: filterDiscrepancyType,
        },
        is_default: false,
      };
      const res = await fetch('/api/saved-filters/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setSaveFilterNameInput('');
        setIsSaveFilterModalOpen(false);
        fetchSavedFilters(authToken);
      } else {
        const err = await res.json();
        alert(`Failed to save filter: ${JSON.stringify(err)}`);
      }
    } catch (err) {
      console.error('Save filter error:', err);
    } finally {
      setIsSavingFilter(false);
    }
  };

  const handleApplySavedFilter = (saved: SavedFilterItem) => {
    setActiveSavedFilterId(saved.id);
    const p = saved.filter_params || {};
    setSearchQuery(p.search || '');
    setStatusFilter(p.status || 'ALL');
    setFilterBank(p.bank || '');
    setFilterMinAmount(p.min_amount || '');
    setFilterMaxAmount(p.max_amount || '');
    setFilterMaturityFrom(p.maturity_from || '');
    setFilterMaturityTo(p.maturity_to || '');
    setFilterDiscrepancyType(p.discrepancy_type || '');
  };

  const handleResetFilters = () => {
    setActiveSavedFilterId(null);
    setSearchQuery('');
    setStatusFilter('ALL');
    setFilterBank('');
    setFilterMinAmount('');
    setFilterMaxAmount('');
    setFilterMaturityFrom('');
    setFilterMaturityTo('');
    setFilterDiscrepancyType('');
  };

  const handleDeleteSavedFilter = async (id: number) => {
    try {
      const res = await fetch(`/api/saved-filters/${id}/`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        if (activeSavedFilterId === id) setActiveSavedFilterId(null);
        fetchSavedFilters(authToken);
      }
    } catch (err) {
      console.error('Delete saved filter error:', err);
    }
  };

  // 9. Phase 6: Reports & Exports
  const handleDownloadReport = async (reportType: string, format: 'csv' | 'pdf') => {
    const downloadKey = `${reportType}-${format}`;
    setDownloadingReportKey(downloadKey);
    try {
      const endpoint = format === 'csv'
        ? `/api/reports/download-csv/?report_type=${encodeURIComponent(reportType)}`
        : `/api/reports/download-pdf/?report_type=${encodeURIComponent(reportType)}`;
      const res = await fetch(endpoint, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `aicte_report_${reportType}_${new Date().toISOString().split('T')[0]}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Report download failed: ${err.error || 'Server error'}`);
      }
    } catch (err) {
      console.error('Download error:', err);
      alert('Failed to download report.');
    } finally {
      setDownloadingReportKey(null);
    }
  };

  const handleSendWeeklySummaryNow = async () => {
    setIsSendingWeeklySummary(true);
    setWeeklySummaryMsg(null);
    try {
      const res = await fetch('/api/reports/send-weekly-summary/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (res.ok) {
        setWeeklySummaryMsg(data.message || 'Weekly compliance summary dispatched successfully to regulatory officials.');
      } else {
        alert(`Dispatch failed: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Send weekly summary error:', err);
      alert('Failed to trigger weekly summary email.');
    } finally {
      setIsSendingWeeklySummary(false);
    }
  };

  // 10. Health Check
  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/health/');
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch (err) {
      console.error('Health check failed:', err);
    }
  };

  useEffect(() => {
    fetchHealth();
    loginUser(USERS[0]);
  }, []);

  const handleUserSwitch = (idx: number) => {
    setCurrentUserIdx(idx);
    setSelectedInstrument(null);
    loginUser(USERS[idx]);
  };

  // Compute SHA-256 preview in browser for user visibility
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setSubmitError('');
    const file = e.target.files?.[0];
    if (!file) {
      setSelectedFile(null);
      setFileHashPreview('');
      return;
    }

    const allowedExts = ['.pdf', '.jpg', '.jpeg', '.png'];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedExts.includes(ext)) {
      setSubmitError(`Invalid file format '${ext}'. Only PDF, JPG, and PNG documents are allowed.`);
      setSelectedFile(null);
      return;
    }

    if (file.size > 15 * 1024 * 1024) {
      setSubmitError('File exceeds 15 MB limit.');
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);

    try {
      const buffer = await file.arrayBuffer();
      const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      setFileHashPreview(hashHex);
    } catch (err) {
      console.error('Could not compute client preview hash:', err);
    }
  };

  // Phase 3: OCR Pre-Scan Handler
  const handleOcrFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setOcrError('');
    const file = e.target.files?.[0];
    if (!file) return;

    setOcrLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/instruments/extract-ocr/', {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setOcrExtractedData(data.extracted);
        setSelectedFile(file);
        const buffer = await file.arrayBuffer();
        const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        setFileHashPreview(hashArray.map(b => b.toString(16).padStart(2, '0')).join(''));
      } else {
        const err = await res.json();
        setOcrError(err.error || 'Failed to extract text from scan.');
      }
    } catch (err) {
      setOcrError('Network error while running OCR extraction.');
    } finally {
      setOcrLoading(false);
    }
  };

  const applyOcrValues = () => {
    if (!ocrExtractedData) return;
    if (ocrExtractedData.reference_number) setRefNumber(ocrExtractedData.reference_number);
    if (ocrExtractedData.issuing_bank) setBankName(ocrExtractedData.issuing_bank);
    if (ocrExtractedData.amount) setAmount(ocrExtractedData.amount);
    if (ocrExtractedData.issue_date) setIssueDate(ocrExtractedData.issue_date);
    if (ocrExtractedData.maturity_date) setMaturityDate(ocrExtractedData.maturity_date);
  };

  // Submit FDR
  const handleSubmitFDR = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    setSubmitSuccess('');

    if (!refNumber || !bankName || !branchName || !ifsc || !amount || !issueDate || !maturityDate) {
      setSubmitError('Please complete all mandatory FDR fields.');
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append('reference_number', refNumber.trim());
    formData.append('instrument_type', 'FDR');
    formData.append('issuing_bank', bankName);
    formData.append('issuing_branch', branchName);
    formData.append('branch_ifsc', ifsc.trim().toUpperCase());
    formData.append('amount', amount);
    formData.append('issue_date', issueDate);
    formData.append('maturity_date', maturityDate);
    formData.append('lien_in_favour_of_aicte', lienMarked ? 'true' : 'false');
    formData.append('joint_holder_name', jointHolder || `${userProfile?.institution_name || 'Institution'} and AICTE`);

    if (replacesId) {
      formData.append('replaces', replacesId);
      formData.append('renewal_type', renewalType);
    }

    if (selectedFile) {
      formData.append('fdr_certificate', selectedFile);
      formData.append('fdr_certificate_type', 'FDR_CERTIFICATE');
    }

    try {
      const res = await fetch('/api/instruments/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
        body: formData,
      });

      if (res.ok) {
        setSubmitSuccess('FDR instrument submitted successfully and encrypted at rest!');
        fetchInstruments(authToken);
        setTimeout(() => {
          setIsSubmitModalOpen(false);
          setRefNumber('');
          setBranchName('');
          setIfsc('');
          setAmount('');
          setSelectedFile(null);
          setFileHashPreview('');
          setOcrExtractedData(null);
          setReplacesId('');
          setRenewalType('REPLACEMENT');
          setSubmitSuccess('');
        }, 1500);
      } else {
        const err = await res.json();
        setSubmitError(typeof err === 'object' ? JSON.stringify(err) : 'Submission failed');
      }
    } catch (err) {
      setSubmitError('Network error while submitting FDR.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Upload New Version of Document inside Detail Modal
  const handleUploadNewVersion = async () => {
    if (!selectedInstrument || !versionFile) return;
    setVersionUploadError('');
    setUploadingVersion(true);

    const formData = new FormData();
    formData.append('file', versionFile);
    formData.append('document_type', versionDocType);

    try {
      const res = await fetch(`/api/instruments/${selectedInstrument.id}/documents/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
        body: formData,
      });

      if (res.ok) {
        setVersionFile(null);
        fetchInstruments(authToken);
        refreshSingleInstrument(selectedInstrument.id);
      } else {
        const err = await res.json();
        setVersionUploadError(typeof err === 'object' ? JSON.stringify(err) : 'Upload failed');
      }
    } catch (err) {
      setVersionUploadError('Network error while uploading version.');
    } finally {
      setUploadingVersion(false);
    }
  };

  // Secure Document Download
  const handleSecureDownload = async (doc: DocumentItem) => {
    try {
      const res = await fetch(`/api/documents/${doc.id}/download/`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      if (!res.ok) {
        alert('Unauthorized or document not found.');
        return;
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.file_name || `document_${doc.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
      alert('Failed to download encrypted file.');
    }
  };

  // Phase 3: Scrutiny Officer Bank Verification Trigger
  const handleBankVerify = async (instId: number) => {
    setIsVerifying(true);
    setLastBankResult(null);
    try {
      const res = await fetch(`/api/instruments/${instId}/verify/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ notes: verifyNotes }),
      });
      if (res.ok) {
        const data = await res.json();
        setLastBankResult(data.bank_verification);
        fetchInstruments(authToken);
        refreshSingleInstrument(instId);
      } else {
        const err = await res.json();
        alert(`Verification failed: ${JSON.stringify(err)}`);
      }
    } catch (err) {
      console.error('Verify error:', err);
    } finally {
      setIsVerifying(false);
    }
  };

  // Phase 3: Resolve Discrepancy Action
  const handleResolveDiscrepancy = async () => {
    if (!selectedInstrument || !resolvingDiscrepancy || !resolutionNote) return;
    setIsResolving(true);
    try {
      const res = await fetch(`/api/instruments/${selectedInstrument.id}/resolve-discrepancy/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          discrepancy_id: resolvingDiscrepancy.id,
          resolution_note: resolutionNote,
        }),
      });
      if (res.ok) {
        setResolvingDiscrepancy(null);
        setResolutionNote('');
        fetchInstruments(authToken);
        refreshSingleInstrument(selectedInstrument.id);
      } else {
        const err = await res.json();
        alert(`Failed to resolve: ${JSON.stringify(err)}`);
      }
    } catch (err) {
      console.error('Resolve error:', err);
    } finally {
      setIsResolving(false);
    }
  };

  // Phase 3: Flag Manual Discrepancy Action
  const handleFlagDiscrepancy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInstrument || !flagReason) return;
    setIsFlagging(true);
    try {
      const res = await fetch(`/api/instruments/${selectedInstrument.id}/flag-discrepancy/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          reason: flagReason,
          field_name: flagFieldName,
          severity: flagSeverity,
        }),
      });
      if (res.ok) {
        setIsFlagModalOpen(false);
        setFlagReason('');
        setFlagFieldName('');
        fetchInstruments(authToken);
        refreshSingleInstrument(selectedInstrument.id);
      } else {
        const err = await res.json();
        alert(`Failed to flag: ${JSON.stringify(err)}`);
      }
    } catch (err) {
      console.error('Flag error:', err);
    } finally {
      setIsFlagging(false);
    }
  };

  // Phase 3: Mark Verified Action
  const handleMarkVerified = async (instId: number) => {
    const notes = prompt('Enter officer verification sign-off notes:', 'Satisfied with all institutional submissions and mock bank reconciliation.');
    if (notes === null) return;
    try {
      const res = await fetch(`/api/instruments/${instId}/mark-verified/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ notes }),
      });
      if (res.ok) {
        fetchInstruments(authToken);
        refreshSingleInstrument(instId);
        alert('Instrument successfully marked as Verified.');
      } else {
        const err = await res.json();
        alert(`Cannot mark verified: ${JSON.stringify(err)}`);
      }
    } catch (err) {
      console.error('Mark verified error:', err);
    }
  };

  // Submit Remark
  const handleAddRemark = async () => {
    if (!selectedInstrument || !newRemarkText) return;
    setIsSubmittingRemark(true);
    try {
      const res = await fetch(`/api/instruments/${selectedInstrument.id}/remarks/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: newRemarkText,
          remark_type: newRemarkType,
          is_internal: false,
        }),
      });
      if (res.ok) {
        setNewRemarkText('');
        fetchInstruments(authToken);
        refreshSingleInstrument(selectedInstrument.id);
      }
    } catch (err) {
      console.error('Add remark error:', err);
    } finally {
      setIsSubmittingRemark(false);
    }
  };

  // Phase 5: Release & Refund Handlers
  const handleRequestRelease = async () => {
    if (!selectedInstrument || !releaseJustification.trim()) {
      alert('Please provide a justification for deposit release/refund.');
      return;
    }
    setIsRequestingRelease(true);
    setReleaseActionError('');
    setReleaseActionSuccess('');
    try {
      const res = await fetch(`/api/instruments/${selectedInstrument.id}/request-release/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ justification: releaseJustification.trim() }),
      });
      if (res.ok) {
        setReleaseActionSuccess('Release & refund application submitted successfully. Now routed for scrutiny.');
        setReleaseJustification('');
        fetchInstruments(authToken);
        refreshSingleInstrument(selectedInstrument.id);
        fetchNotifications(authToken);
      } else {
        const err = await res.json();
        setReleaseActionError(typeof err === 'object' ? JSON.stringify(err) : 'Failed to submit release request.');
      }
    } catch (err) {
      console.error('Request release error:', err);
      setReleaseActionError('Network error while requesting release.');
    } finally {
      setIsRequestingRelease(false);
    }
  };

  const handleScrutinizeRelease = async () => {
    if (!selectedInstrument) return;
    setIsScrutinizing(true);
    setReleaseActionError('');
    setReleaseActionSuccess('');
    try {
      const res = await fetch(`/api/instruments/${selectedInstrument.id}/scrutinize-release/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          recommendation: scrutinyRecommendation,
          notes: scrutinyNotes,
        }),
      });
      if (res.ok) {
        setReleaseActionSuccess('Scrutiny findings recorded and routed to Approving Authority.');
        fetchInstruments(authToken);
        refreshSingleInstrument(selectedInstrument.id);
        fetchNotifications(authToken);
      } else {
        const err = await res.json();
        setReleaseActionError(typeof err === 'object' ? JSON.stringify(err) : 'Failed to scrutinize release.');
      }
    } catch (err) {
      console.error('Scrutinize release error:', err);
      setReleaseActionError('Network error during release scrutiny.');
    } finally {
      setIsScrutinizing(false);
    }
  };

  const handleApproveRelease = async () => {
    if (!selectedInstrument) return;
    if (!sanctionOrderRef.trim()) {
      alert('Please enter the official Release Sanction Order Reference.');
      return;
    }
    setIsSanctioning(true);
    setReleaseActionError('');
    setReleaseActionSuccess('');
    try {
      const res = await fetch(`/api/instruments/${selectedInstrument.id}/approve-release/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          order_reference: sanctionOrderRef.trim(),
          notes: sanctionNotes,
        }),
      });
      if (res.ok) {
        setReleaseActionSuccess('Official Release & Refund Order Sanctioned! Status transitioned to Released.');
        setSanctionOrderRef('');
        setSanctionNotes('');
        fetchInstruments(authToken);
        refreshSingleInstrument(selectedInstrument.id);
        fetchNotifications(authToken);
      } else {
        const err = await res.json();
        setReleaseActionError(typeof err === 'object' ? JSON.stringify(err) : 'Failed to approve release.');
      }
    } catch (err) {
      console.error('Approve release error:', err);
      setReleaseActionError('Network error during release approval.');
    } finally {
      setIsSanctioning(false);
    }
  };

  const handleRejectRelease = async () => {
    if (!selectedInstrument || !rejectionReasonInput.trim()) {
      alert('Please enter a formal reason for rejecting the release application.');
      return;
    }
    setIsRejecting(true);
    setReleaseActionError('');
    setReleaseActionSuccess('');
    try {
      const res = await fetch(`/api/instruments/${selectedInstrument.id}/reject-release/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rejection_reason: rejectionReasonInput.trim(),
        }),
      });
      if (res.ok) {
        setReleaseActionSuccess('Release application rejected with statutory notification dispatched to the institution.');
        setRejectionReasonInput('');
        fetchInstruments(authToken);
        refreshSingleInstrument(selectedInstrument.id);
        fetchNotifications(authToken);
      } else {
        const err = await res.json();
        setReleaseActionError(typeof err === 'object' ? JSON.stringify(err) : 'Failed to reject release.');
      }
    } catch (err) {
      console.error('Reject release error:', err);
      setReleaseActionError('Network error during release rejection.');
    } finally {
      setIsRejecting(false);
    }
  };

  const handleToggleComplianceHold = async () => {
    if (!selectedInstrument) return;
    const willHold = !selectedInstrument.compliance_hold;
    let reason = holdReason;
    if (willHold && !reason.trim()) {
      const input = prompt('Enter statutory compliance hold reason (e.g., Pending dispute, CBI inquiry, audit block):');
      if (!input) return;
      reason = input;
    }
    setIsTogglingHold(true);
    try {
      const res = await fetch(`/api/instruments/${selectedInstrument.id}/compliance-hold/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          compliance_hold: willHold,
          reason: reason || 'Statutory hold updated',
        }),
      });
      if (res.ok) {
        setHoldReason('');
        fetchInstruments(authToken);
        refreshSingleInstrument(selectedInstrument.id);
      } else {
        const err = await res.json();
        alert(`Failed to update compliance hold: ${JSON.stringify(err)}`);
      }
    } catch (err) {
      console.error('Compliance hold toggle error:', err);
    } finally {
      setIsTogglingHold(false);
    }
  };

  // Filter instruments with Phase 6 multi-parameter filter capabilities
  const filteredInstruments = instruments.filter(item => {
    const q = searchQuery.toLowerCase().trim();
    const matchesSearch =
      !q ||
      item.reference_number.toLowerCase().includes(q) ||
      item.issuing_bank.toLowerCase().includes(q) ||
      item.institution_name.toLowerCase().includes(q) ||
      (item.issuing_branch && item.issuing_branch.toLowerCase().includes(q)) ||
      (item.branch_ifsc && item.branch_ifsc.toLowerCase().includes(q));

    const matchesStatus =
      statusFilter === 'ALL' ||
      item.status.toLowerCase() === statusFilter.toLowerCase();

    const matchesBank =
      !filterBank ||
      item.issuing_bank.toLowerCase().includes(filterBank.toLowerCase());

    const numAmt = parseFloat(item.amount || '0');
    const matchesMinAmount =
      !filterMinAmount || numAmt >= parseFloat(filterMinAmount);
    const matchesMaxAmount =
      !filterMaxAmount || numAmt <= parseFloat(filterMaxAmount);

    const matchesMaturityFrom =
      !filterMaturityFrom || (item.maturity_date && item.maturity_date >= filterMaturityFrom);
    const matchesMaturityTo =
      !filterMaturityTo || (item.maturity_date && item.maturity_date <= filterMaturityTo);

    const matchesDiscrepancyType =
      !filterDiscrepancyType ||
      (filterDiscrepancyType === 'HAS_ANY' && item.discrepancies && item.discrepancies.length > 0) ||
      (filterDiscrepancyType === 'NONE' && (!item.discrepancies || item.discrepancies.length === 0)) ||
      (item.discrepancies && item.discrepancies.some(d => d.rule_code === filterDiscrepancyType || d.severity === filterDiscrepancyType));

    return (
      matchesSearch &&
      matchesStatus &&
      matchesBank &&
      matchesMinAmount &&
      matchesMaxAmount &&
      matchesMaturityFrom &&
      matchesMaturityTo &&
      matchesDiscrepancyType
    );
  });

  // Filter notifications
  const filteredNotifications = notifications.filter(n => {
    if (notifTab === 'unread') return !n.is_read;
    return true;
  });

  // Calculate statistics
  const totalValue = instruments.reduce((sum, item) => sum + parseFloat(item.amount || '0'), 0);
  const verifiedCount = instruments.filter(i => i.status === 'Verified' || i.status === 'Active').length;
  const expiringCount = instruments.filter(i => i.status === 'Expiring').length;
  const maturedCount = instruments.filter(i => i.status === 'Matured').length;
  const discrepancyCount = instruments.filter(i => i.status === 'Discrepancy').length;

  const effectiveDisplayDate = simulatedDateInfo?.effective_date || new Date().toISOString().split('T')[0];

  return (
    <div className="portal-container">
      {/* Header */}
      <header className="portal-header">
        <div className="brand-section">
          <div className="gov-emblem">AICTE</div>
          <div>
            <h1 className="portal-title">AICTE Security Deposit & FDR Management Portal</h1>
            <p className="portal-subtitle">Regulation Bureau • Autonomous Maturity Engine & Escalation System</p>
          </div>
        </div>

        <div className="header-right">
          <div className="user-selector-bar">
            <span className="user-selector-label">Role:</span>
            <select
              className="user-select"
              value={currentUserIdx}
              onChange={e => handleUserSwitch(parseInt(e.target.value))}
            >
              {USERS.map((u, i) => (
                <option key={u.username} value={i}>
                  {u.label}
                </option>
              ))}
            </select>
          </div>

          {/* Phase 4 Notification Center Bell */}
          <button
            className="notif-bell-btn"
            title="Alerts & Compliance Notifications"
            onClick={() => setIsNotifModalOpen(true)}
          >
            <span>🔔</span>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Alerts</span>
            {unreadNotifCount > 0 && <span className="notif-badge-count">{unreadNotifCount}</span>}
          </button>

          {/* Phase 4 Admin Policy Rules Button */}
          {USERS[currentUserIdx].role === 'ADMIN' && (
            <button
              className="btn-secondary"
              style={{ fontSize: '0.8rem', padding: '0.45rem 0.8rem' }}
              onClick={() => setIsRulesModalOpen(true)}
            >
              ⚙️ Policy Rules
            </button>
          )}

          {/* Phase 6 Reports & Analytics Button */}
          {(USERS[currentUserIdx].role === 'ADMIN' || USERS[currentUserIdx].role === 'SCRUTINY_OFFICER' || USERS[currentUserIdx].role === 'APPROVING_AUTHORITY') && (
            <button
              className="btn-secondary"
              style={{ fontSize: '0.8rem', padding: '0.45rem 0.8rem', background: 'rgba(59, 130, 246, 0.15)', borderColor: 'rgba(59, 130, 246, 0.4)', color: '#93c5fd' }}
              onClick={() => {
                setWeeklySummaryMsg(null);
                setIsReportsModalOpen(true);
              }}
            >
              📊 Compliance Reports
            </button>
          )}

          {health?.status === 'healthy' ? (
            <div className="system-status-pill">
              <span className="status-dot"></span> Core API Operational
            </div>
          ) : (
            <div className="system-status-pill degraded">
              <span className="status-dot"></span> System Degraded
            </div>
          )}
        </div>
      </header>

      {/* User Context Banner */}
      <div style={{ marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Logged in as: </span>
          <strong style={{ color: '#fff' }}>{userProfile?.username || USERS[currentUserIdx].username}</strong>
          <span className="badge badge-version" style={{ marginLeft: '0.6rem' }}>
            {userProfile?.role || USERS[currentUserIdx].role}
          </span>
          {userProfile?.institution_name && (
            <span style={{ marginLeft: '0.6rem', fontSize: '0.82rem', color: 'var(--accent-saffron)' }}>
              ({userProfile.institution_name} • ID: {userProfile.aicte_id})
            </span>
          )}
        </div>

        {USERS[currentUserIdx].role === 'INSTITUTION' && (
          <button className="btn-primary" onClick={() => setIsSubmitModalOpen(true)}>
            + Submit New FDR
          </button>
        )}
      </div>

      {/* PHASE 4: TIME-TRAVEL DEMO CONTROLLER BAR (ADMIN / TESTING) */}
      {(USERS[currentUserIdx].role === 'ADMIN' || USERS[currentUserIdx].role === 'SCRUTINY_OFFICER') && (
        <div className="time-travel-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff' }}>
              ⏱️ Simulated System Date Engine:
            </span>
            <span
              className={simulatedDateInfo?.is_active ? 'sim-active-badge' : 'sim-real-badge'}
            >
              {simulatedDateInfo?.is_active ? `SIMULATED: ${simulatedDateInfo.effective_date}` : `REAL TODAY: ${effectiveDisplayDate}`}
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              (Guarded: Non-Production Mode)
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <input
              type="date"
              className="form-input"
              style={{ fontSize: '0.78rem', padding: '0.35rem 0.6rem', background: 'rgba(0,0,0,0.5)' }}
              value={customSimDateInput}
              onChange={e => setCustomSimDateInput(e.target.value)}
            />
            <button
              className="btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.35rem 0.7rem' }}
              onClick={() => handleSetSimulatedDate(customSimDateInput)}
            >
              Set Date
            </button>
            {simulatedDateInfo?.is_active && (
              <button
                className="btn-secondary"
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.7rem', color: 'var(--accent-saffron)' }}
                onClick={() => handleSetSimulatedDate(null)}
              >
                Reset to Today
              </button>
            )}
            <button
              className="btn-primary"
              style={{ fontSize: '0.75rem', padding: '0.35rem 0.8rem' }}
              disabled={isRunningMonitoringJob}
              onClick={handleRunMonitoringJob}
            >
              {isRunningMonitoringJob ? 'Evaluating Celery Task...' : '⚡ Run Daily Monitoring Job'}
            </button>
          </div>
        </div>
      )}

      {/* Monitoring Job Result Toast Banner */}
      {monitoringJobResult && (
        <div className="alert-box success" style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <strong>✓ Daily Lifecycle Monitoring Job Executed Successfully for {monitoringJobResult.effective_date}</strong>
            <div style={{ fontSize: '0.78rem', marginTop: '0.25rem', color: '#cbd5e1' }}>
              Evaluated {monitoringJobResult.instruments_evaluated} records • Transitions: {monitoringJobResult.status_transitions?.to_expiring} Expiring, {monitoringJobResult.status_transitions?.to_matured} Matured, {monitoringJobResult.status_transitions?.to_active} Active • Reminders: {monitoringJobResult.reminders_dispatched} Sent • Escalations: {monitoringJobResult.escalations_triggered} Triggered • Overdue: {monitoringJobResult.overdue_flagged}
            </div>
          </div>
          <button className="modal-close" style={{ color: '#fff', fontSize: '1.2rem' }} onClick={() => setMonitoringJobResult(null)}>
            &times;
          </button>
        </div>
      )}

      {/* PHASE 6: ROLE-SPECIFIC COMPLIANCE DASHBOARDS */}
      {USERS[currentUserIdx].role !== 'INSTITUTION' ? (
        <div style={{ marginBottom: '2rem' }}>
          {/* Sub-navigation tabs for Officer Dashboard */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div className="tab-nav" style={{ margin: 0 }}>
              <button
                className={`tab-btn ${officerTab === 'kpi' ? 'active' : ''}`}
                onClick={() => setOfficerTab('kpi')}
              >
                📊 KPI Metrics & Buckets
              </button>
              <button
                className={`tab-btn ${officerTab === 'timeline' ? 'active' : ''}`}
                onClick={() => setOfficerTab('timeline')}
              >
                📅 12-Month Expiry Forecast
              </button>
              <button
                className={`tab-btn ${officerTab === 'risk' ? 'active' : ''}`}
                onClick={() => setOfficerTab('risk')}
              >
                ⚠️ Risk-Ranked Worklist ({officerDashboard?.risk_worklist?.length || 0})
              </button>
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {loadingDashboard && <span style={{ color: 'var(--accent-saffron)', fontSize: '0.72rem' }}>Refreshing metrics...</span>}
              <span>Evaluation Date: <strong style={{ color: '#fff' }}>{officerDashboard?.effective_date || effectiveDisplayDate}</strong></span>
            </div>
          </div>

          {/* TAB 1: KPI OVERVIEW */}
          {officerTab === 'kpi' && (
            <div>
              <div className="kpi-grid-6">
                <div className="kpi-card-rich">
                  <div className="kpi-card-title">Active Deposits</div>
                  <div className="kpi-card-val" style={{ color: 'var(--accent-emerald)' }}>
                    {officerDashboard?.counts?.active ?? verifiedCount}
                  </div>
                  <div className="kpi-card-meta">
                    ₹{((officerDashboard?.counts?.active_amount ?? totalValue) / 100000).toFixed(2)} Lakhs Total Active
                  </div>
                </div>

                <div className="kpi-card-rich">
                  <div className="kpi-card-title">Expiring Soon (90d)</div>
                  <div className="kpi-card-val" style={{ color: 'var(--accent-saffron)' }}>
                    {officerDashboard?.counts?.expiring_total ?? expiringCount}
                  </div>
                  <div className="kpi-card-meta" style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginTop: '0.2rem' }}>
                    <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', fontSize: '0.65rem' }}>
                      0-30d: {officerDashboard?.counts?.expiring_30 ?? 0}
                    </span>
                    <span className="badge" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24', fontSize: '0.65rem' }}>
                      31-60d: {officerDashboard?.counts?.expiring_60 ?? 0}
                    </span>
                    <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', fontSize: '0.65rem' }}>
                      61-90d: {officerDashboard?.counts?.expiring_90 ?? 0}
                    </span>
                  </div>
                </div>

                <div className="kpi-card-rich">
                  <div className="kpi-card-title">Matured / Overdue</div>
                  <div className="kpi-card-val" style={{ color: 'var(--accent-rose)' }}>
                    {officerDashboard?.counts?.matured ?? maturedCount}
                  </div>
                  <div className="kpi-card-meta">Action Required Immediately</div>
                </div>

                <div className="kpi-card-rich">
                  <div className="kpi-card-title">Pending Verification</div>
                  <div className="kpi-card-val" style={{ color: '#38bdf8' }}>
                    {officerDashboard?.counts?.pending_verification ?? 0}
                  </div>
                  <div className="kpi-card-meta">Awaiting Bank CBS Scrutiny</div>
                </div>

                <div className="kpi-card-rich">
                  <div className="kpi-card-title">Open Discrepancies</div>
                  <div className="kpi-card-val" style={{ color: '#fb7185' }}>
                    {officerDashboard?.counts?.discrepancies ?? discrepancyCount}
                  </div>
                  <div className="kpi-card-meta">Audit Discrepancy Flags</div>
                </div>

                <div className="kpi-card-rich">
                  <div className="kpi-card-title">National Deposit Corpus</div>
                  <div className="kpi-card-val" style={{ color: '#f8fafc' }}>
                    ₹{((officerDashboard?.counts?.total_amount ?? totalValue) / 10000000).toFixed(2)} Cr
                  </div>
                  <div className="kpi-card-meta">
                    Across {officerDashboard?.counts?.total_instruments ?? instruments.length} Instruments
                  </div>
                </div>
              </div>

              {/* Bank Exposure Distribution Bar */}
              {officerDashboard?.bank_distribution && officerDashboard.bank_distribution.length > 0 && (
                <div style={{ marginTop: '1rem', background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem 1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Issuing Bank Exposure:
                  </span>
                  <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', flex: 1 }}>
                    {officerDashboard.bank_distribution.slice(0, 6).map(b => (
                      <span key={b.bank} style={{ fontSize: '0.72rem', background: 'rgba(255,255,255,0.05)', padding: '0.2rem 0.5rem', borderRadius: '4px', border: '1px solid var(--border-color)', color: '#cbd5e1' }}>
                        <strong style={{ color: '#fff' }}>{b.bank}</strong>: {b.count} FDRs (₹{(b.total_amount / 100000).toFixed(1)}L)
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: 12-MONTH EXPIRY TIMELINE FORECAST */}
          {officerTab === 'timeline' && (
            <div className="chart-container-box">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                    📅 12-Month Forward Expiry Exposure Forecast
                  </h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.2rem 0 0' }}>
                    Projected monthly maturity distribution of AICTE security deposits across all approved institutions.
                  </p>
                </div>
              </div>

              {/* Chart visualization bars */}
              <div className="timeline-chart-bars">
                {officerDashboard?.expiry_timeline?.map(m => {
                  const maxAmt = Math.max(...(officerDashboard?.expiry_timeline?.map(x => x.total_amount) || [1]), 100000);
                  const heightPercent = m.total_amount > 0 ? Math.max(14, Math.round((m.total_amount / maxAmt) * 100)) : 4;
                  return (
                    <div key={m.month_key} className="timeline-bar-column">
                      <div style={{ fontSize: '0.68rem', fontWeight: 700, color: m.count > 0 ? 'var(--accent-saffron)' : '#64748b', marginBottom: '0.3rem', textAlign: 'center' }}>
                        {m.count > 0 ? `${m.count}` : ''}
                      </div>
                      <div className="timeline-bar-wrapper">
                        <div
                          className="timeline-bar-fill"
                          style={{
                            height: `${heightPercent}%`,
                            background: m.count > 0
                              ? 'linear-gradient(180deg, #f59e0b 0%, #d97706 100%)'
                              : 'rgba(255, 255, 255, 0.05)',
                          }}
                          title={`${m.month_label}: ${m.count} deposits maturing (₹${(m.total_amount / 100000).toFixed(2)} Lakhs)`}
                        />
                      </div>
                      <div className="timeline-bar-month">
                        {m.month_label.split(' ')[0]}
                      </div>
                      <div style={{ fontSize: '0.62rem', color: '#94a3b8', textAlign: 'center' }}>
                        {m.count > 0 ? `₹${(m.total_amount / 100000).toFixed(0)}L` : '-'}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 3: RISK-RANKED WORKLIST */}
          {officerTab === 'risk' && (
            <div className="risk-worklist-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                    ⚠️ Risk-Ranked Regulatory Worklist
                  </h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.2rem 0 0' }}>
                    Composite AICTE risk score (0-100) prioritizing deposits by maturity proximity, discrepancy severity, verification gaps, exposure amount, and past institutional renewal delays.
                  </p>
                </div>
              </div>

              {!officerDashboard?.risk_worklist || officerDashboard.risk_worklist.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  ✓ No high-risk security deposits requiring immediate intervention.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="portal-table" style={{ fontSize: '0.8rem' }}>
                    <thead>
                      <tr>
                        <th>Risk Score</th>
                        <th>Tier</th>
                        <th>FDR Reference</th>
                        <th>Institution</th>
                        <th>Issuing Bank & Amount</th>
                        <th>Days to Maturity</th>
                        <th>Risk Factors</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {officerDashboard.risk_worklist.map(r => (
                        <tr key={r.id}>
                          <td>
                            <div className="risk-score-gauge">
                              <strong style={{ color: r.risk_score >= 70 ? '#f87171' : r.risk_score >= 50 ? '#fbbf24' : '#60a5fa' }}>
                                {r.risk_score}
                              </strong>
                              <div className="risk-bar-container">
                                <div
                                  className="risk-bar-indicator"
                                  style={{
                                    width: `${r.risk_score}%`,
                                    background: r.risk_score >= 70 ? '#ef4444' : r.risk_score >= 50 ? '#f59e0b' : '#3b82f6',
                                  }}
                                />
                              </div>
                            </div>
                          </td>
                          <td>
                            <span className={`risk-tier-pill risk-tier-${r.risk_tier.toLowerCase()}`}>
                              {r.risk_tier}
                            </span>
                          </td>
                          <td>
                            <strong style={{ color: '#fff' }}>{r.reference_number}</strong>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{r.status}</div>
                          </td>
                          <td>
                            <div style={{ fontWeight: 600, color: '#f1f5f9' }}>{r.institution_name}</div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>AICTE: {r.institution_aicte_id}</div>
                          </td>
                          <td>
                            <div>{r.issuing_bank}</div>
                            <strong style={{ color: '#cbd5e1' }}>
                              ₹{parseFloat(r.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </strong>
                          </td>
                          <td>
                            {r.days_to_maturity !== null ? (
                              <span style={{ color: r.days_to_maturity <= 0 ? '#f87171' : r.days_to_maturity <= 30 ? '#fbbf24' : '#fff', fontWeight: 600 }}>
                                {r.days_to_maturity <= 0 ? `Overdue (${Math.abs(r.days_to_maturity)}d)` : `${r.days_to_maturity} days`}
                              </span>
                            ) : (
                              '-'
                            )}
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', maxWidth: '280px' }}>
                              {r.risk_factors.map((f, i) => (
                                <span key={i} className="badge" style={{ fontSize: '0.65rem', background: 'rgba(255, 255, 255, 0.06)', color: '#cbd5e1' }}>
                                  {f}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td>
                            <button
                              className="btn-secondary"
                              style={{ fontSize: '0.72rem', padding: '0.3rem 0.6rem' }}
                              onClick={() => {
                                const found = instruments.find(i => i.id === r.id);
                                if (found) setSelectedInstrument(found);
                              }}
                            >
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* INSTITUTION DASHBOARD: SUMMARY & UPCOMING DEADLINES */
        <div style={{ marginBottom: '2rem' }}>
          <div className="stats-grid" style={{ marginBottom: '1.25rem' }}>
            <div className="stat-card">
              <div className="stat-label">Active Pledged Deposits</div>
              <div className="stat-value" style={{ color: 'var(--accent-emerald)' }}>
                {institutionDashboard?.summary?.active_count ?? verifiedCount}
              </div>
              <div className="stat-meta">
                ₹{((institutionDashboard?.summary?.total_amount ?? totalValue) / 100000).toFixed(2)} Lakhs Total Value
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Expiring Soon</div>
              <div className="stat-value" style={{ color: (institutionDashboard?.summary?.expiring_count ?? 0) > 0 ? 'var(--accent-saffron)' : '#fff' }}>
                {institutionDashboard?.summary?.expiring_count ?? expiringCount}
              </div>
              <div className="stat-meta">Action Required Before Maturity</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Matured / Overdue</div>
              <div className="stat-value" style={{ color: (institutionDashboard?.summary?.matured_count ?? 0) > 0 ? 'var(--accent-rose)' : '#fff' }}>
                {institutionDashboard?.summary?.matured_count ?? maturedCount}
              </div>
              <div className="stat-meta">Submit Replacement FDR</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Under Scrutiny / Discrepancy</div>
              <div className="stat-value" style={{ color: (institutionDashboard?.summary?.discrepancy_count ?? 0) > 0 ? '#fb7185' : '#38bdf8' }}>
                {(institutionDashboard?.summary?.under_scrutiny_count ?? 0) + (institutionDashboard?.summary?.discrepancy_count ?? discrepancyCount)}
              </div>
              <div className="stat-meta">AICTE Officer Review Active</div>
            </div>
          </div>

          {/* Upcoming Deadlines Console */}
          <div className="risk-worklist-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                  ⏱️ Upcoming Deposit Deadlines & Compliance Actions
                </h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.2rem 0 0' }}>
                  Institutional deadline tracker for maturity renewal, bank verification, and release eligibility.
                </p>
              </div>
            </div>

            {!institutionDashboard?.upcoming_deadlines || institutionDashboard.upcoming_deadlines.length === 0 ? (
              <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.02)', borderRadius: '6px' }}>
                ✓ No immediate deposit deadlines or compliance actions required for your institution.
              </div>
            ) : (
              <div className="deadlines-list">
                {institutionDashboard.upcoming_deadlines.map(d => (
                  <div key={d.id} className={`deadline-item-card ${d.urgency.toLowerCase()}`}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.3rem' }}>
                        <strong style={{ color: '#fff', fontSize: '0.95rem' }}>{d.reference_number}</strong>
                        <span className={`risk-tier-pill risk-tier-${d.urgency === 'OVERDUE' ? 'critical' : d.urgency.toLowerCase()}`}>
                          {d.urgency}
                        </span>
                        <span className={`badge badge-status-${d.status.toLowerCase().replace(' ', '-')}`}>
                          {d.status}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        {d.issuing_bank} • ₹{parseFloat(d.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })} • Matures on <strong style={{ color: '#e2e8f0' }}>{d.maturity_date}</strong>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '0.82rem', fontWeight: 700, color: d.days_left <= 0 ? '#f87171' : d.days_left <= 30 ? '#fbbf24' : '#60a5fa' }}>
                          {d.days_left <= 0 ? `OVERDUE BY ${Math.abs(d.days_left)} DAYS` : `${d.days_left} DAYS LEFT`}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                          {d.action_required}
                        </div>
                      </div>
                      <button
                        className="btn-primary"
                        style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
                        onClick={() => {
                          const found = instruments.find(i => i.id === d.id);
                          if (found) {
                            setSelectedInstrument(found);
                            if (d.days_left <= 30) setModalTab('lineage');
                          }
                        }}
                      >
                        Action Needed →
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* PHASE 6: RICH SEARCH & MULTI-PARAMETER FILTERS BAR */}
      <div className="filter-bar-rich">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          <h2 className="section-title" style={{ margin: 0, fontSize: '1.1rem' }}>
            {USERS[currentUserIdx].role === 'INSTITUTION'
              ? 'Institutional Fixed Deposit Receipts'
              : 'National Institution Deposit Directory'}
          </h2>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            {(searchQuery || statusFilter !== 'ALL' || filterBank || filterMinAmount || filterMaxAmount || filterMaturityFrom || filterMaturityTo || filterDiscrepancyType) && (
              <button
                className="btn-secondary"
                style={{ fontSize: '0.72rem', padding: '0.3rem 0.6rem', color: 'var(--text-muted)' }}
                onClick={handleResetFilters}
              >
                Reset Filters
              </button>
            )}
            <button
              className="btn-secondary"
              style={{ fontSize: '0.72rem', padding: '0.3rem 0.65rem', borderColor: 'var(--accent-saffron)', color: 'var(--accent-saffron)' }}
              onClick={() => setIsSaveFilterModalOpen(true)}
            >
              ⭐ Save Preset
            </button>
          </div>
        </div>

        {/* Primary Filter Row */}
        <div className="filter-controls-row">
          <input
            type="text"
            className="filter-input-sm"
            style={{ minWidth: '220px', flex: 1 }}
            placeholder="Search FDR number, bank, institution, branch..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />

          <select
            className="filter-input-sm"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Statuses</option>
            <option value="Submitted">Submitted</option>
            <option value="Under Scrutiny">Under Scrutiny</option>
            <option value="Verified">Verified</option>
            <option value="Active">Active</option>
            <option value="Expiring">Expiring</option>
            <option value="Matured">Matured</option>
            <option value="Discrepancy">Discrepancy</option>
            <option value="Release Requested">Release Requested</option>
            <option value="Released">Released</option>
            <option value="Replaced">Replaced</option>
          </select>

          <select
            className="filter-input-sm"
            value={filterBank}
            onChange={e => setFilterBank(e.target.value)}
          >
            <option value="">All Issuing Banks</option>
            <option value="State Bank of India">State Bank of India</option>
            <option value="HDFC Bank">HDFC Bank</option>
            <option value="Punjab National Bank">Punjab National Bank</option>
            <option value="ICICI Bank">ICICI Bank</option>
            <option value="Canara Bank">Canara Bank</option>
            <option value="Bank of Baroda">Bank of Baroda</option>
            <option value="Axis Bank">Axis Bank</option>
          </select>

          <select
            className="filter-input-sm"
            value={filterDiscrepancyType}
            onChange={e => setFilterDiscrepancyType(e.target.value)}
          >
            <option value="">All Discrepancy Status</option>
            <option value="HAS_ANY">⚠️ Has Open Discrepancies</option>
            <option value="NONE">✓ Clean (No Discrepancies)</option>
            <option value="CRITICAL">Critical Severity Discrepancies</option>
            <option value="HIGH">High Severity Discrepancies</option>
            <option value="DUPLICATE_FDR_NUMBER">Duplicate FDR Number</option>
            <option value="AMOUNT_MISMATCH_BANK">Bank Amount Mismatch</option>
            <option value="MATURITY_BEFORE_ISSUE">Maturity Before Issue</option>
            <option value="MISSING_LIEN_LETTER">Missing Lien Letter</option>
            <option value="MISSING_MANDATORY_DOCUMENTS">Missing Mandatory Docs</option>
          </select>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Amount (₹):</span>
            <input
              type="number"
              className="filter-input-sm"
              style={{ width: '90px' }}
              placeholder="Min"
              value={filterMinAmount}
              onChange={e => setFilterMinAmount(e.target.value)}
            />
            <span style={{ color: 'var(--text-muted)' }}>-</span>
            <input
              type="number"
              className="filter-input-sm"
              style={{ width: '90px' }}
              placeholder="Max"
              value={filterMaxAmount}
              onChange={e => setFilterMaxAmount(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Matures:</span>
            <input
              type="date"
              className="filter-input-sm"
              value={filterMaturityFrom}
              onChange={e => setFilterMaturityFrom(e.target.value)}
              title="Maturity From"
            />
            <span style={{ color: 'var(--text-muted)' }}>to</span>
            <input
              type="date"
              className="filter-input-sm"
              value={filterMaturityTo}
              onChange={e => setFilterMaturityTo(e.target.value)}
              title="Maturity To"
            />
          </div>
        </div>

        {/* Saved Filters Preset Pills */}
        {savedFilters.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', paddingTop: '0.4rem', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600 }}>Saved Presets:</span>
            {savedFilters.map(f => (
              <span
                key={f.id}
                className={`saved-filter-pill ${activeSavedFilterId === f.id ? 'active' : ''}`}
                onClick={() => handleApplySavedFilter(f)}
              >
                <span>⭐ {f.name}</span>
                <span
                  style={{ color: '#94a3b8', marginLeft: '0.2rem', cursor: 'pointer', fontWeight: 'bold' }}
                  onClick={e => {
                    e.stopPropagation();
                    handleDeleteSavedFilter(f.id);
                  }}
                  title="Delete preset"
                >
                  &times;
                </span>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Instruments Table */}
      <div className="table-card">
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading instruments...
          </div>
        ) : filteredInstruments.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <p>No deposit records found for this institution profile.</p>
            {USERS[currentUserIdx].role === 'INSTITUTION' && (
              <button
                className="btn-primary"
                style={{ marginTop: '1rem' }}
                onClick={() => setIsSubmitModalOpen(true)}
              >
                Submit First FDR
              </button>
            )}
          </div>
        ) : (
          <table className="portal-table">
            <thead>
              <tr>
                <th>FDR Reference</th>
                <th>Issuing Bank & Branch</th>
                <th>Principal Amount</th>
                <th>Maturity Date</th>
                <th>Trust Score</th>
                <th>Status</th>
                <th>Documents</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredInstruments.map(item => (
                <tr key={item.id}>
                  <td>
                    <strong style={{ color: '#fff', cursor: 'pointer' }} onClick={() => setSelectedInstrument(item)}>
                      {item.reference_number}
                    </strong>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                      {item.institution_name}
                    </div>
                  </td>
                  <td>
                    <div>{item.issuing_bank}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      IFSC: {item.branch_ifsc}
                    </div>
                  </td>
                  <td>
                    <strong style={{ color: '#f8fafc' }}>
                      ₹{parseFloat(item.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </strong>
                  </td>
                  <td>
                    <div>{item.maturity_date}</div>
                    {item.status === 'Expiring' && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--accent-saffron)', fontWeight: 600 }}>
                        Expiring Soon
                      </div>
                    )}
                    {item.status === 'Matured' && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--accent-rose)', fontWeight: 700 }}>
                        Matured / Action Needed
                      </div>
                    )}
                  </td>
                  <td>
                    <span
                      className={`trust-pill ${
                        item.trust_score >= 80 ? 'trust-high' : item.trust_score >= 50 ? 'trust-medium' : 'trust-low'
                      }`}
                    >
                      🛡️ {item.trust_score}/100
                    </span>
                  </td>
                  <td>
                    <span className={`badge badge-status-${item.status.toLowerCase().replace(' ', '-')}`}>
                      {item.status}
                    </span>
                  </td>
                  <td>
                    <span className="badge-hash" style={{ cursor: 'pointer' }} onClick={() => setSelectedInstrument(item)}>
                      {item.documents?.length || 0} file(s)
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <button
                        className="btn-secondary"
                        onClick={() => setSelectedInstrument(item)}
                      >
                        Inspect
                      </button>
                      {USERS[currentUserIdx].role === 'SCRUTINY_OFFICER' && item.status === 'Submitted' && (
                        <button
                          className="btn-primary"
                          style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                          onClick={() => handleBankVerify(item.id)}
                        >
                          Verify
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* PHASE 4: NOTIFICATIONS MODAL / DRAWER */}
      {isNotifModalOpen && (
        <div className="modal-overlay" onClick={() => setIsNotifModalOpen(false)}>
          <div className="modal-content" style={{ maxWidth: '680px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <h3 className="modal-title">🔔 Regulatory Alerts & Notifications</h3>
                {unreadNotifCount > 0 && <span className="notif-badge-count">{unreadNotifCount} New</span>}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                {unreadNotifCount > 0 && (
                  <button
                    className="btn-secondary"
                    style={{ fontSize: '0.72rem', padding: '0.3rem 0.6rem' }}
                    onClick={handleMarkAllNotifsRead}
                  >
                    Mark All Read
                  </button>
                )}
                <button className="modal-close" onClick={() => setIsNotifModalOpen(false)}>&times;</button>
              </div>
            </div>

            <div className="tab-nav" style={{ marginBottom: '1rem' }}>
              <button
                className={`tab-btn ${notifTab === 'all' ? 'active' : ''}`}
                onClick={() => setNotifTab('all')}
              >
                All Alerts ({notifications.length})
              </button>
              <button
                className={`tab-btn ${notifTab === 'unread' ? 'active' : ''}`}
                onClick={() => setNotifTab('unread')}
              >
                Unread ({unreadNotifCount})
              </button>
            </div>

            {filteredNotifications.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No notifications to display in this view.
              </div>
            ) : (
              <div style={{ maxHeight: '60vh', overflowY: 'auto' }}>
                {filteredNotifications.map(notif => (
                  <div
                    key={notif.id}
                    className={`notif-card ${!notif.is_read ? 'is-unread' : ''}`}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.4rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <span className={`notif-channel-pill notif-channel-${notif.channel.toLowerCase()}`}>
                          {notif.channel}
                        </span>
                        <span className={`notif-type-pill notif-type-${notif.notification_type.toLowerCase()}`}>
                          {notif.notification_type}
                        </span>
                        {notif.offset_days && (
                          <span className="badge-hash">{notif.offset_days} Days Out</span>
                        )}
                        <strong style={{ color: '#fff', fontSize: '0.85rem' }}>{notif.title}</strong>
                      </div>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {new Date(notif.sent_at).toLocaleString()}
                      </span>
                    </div>

                    <p style={{ fontSize: '0.8rem', color: '#cbd5e1', marginTop: '0.4rem', lineHeight: 1.4 }}>
                      {notif.message}
                    </p>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        Target: {notif.recipient_role || 'User'} {notif.instrument_reference ? `• ${notif.instrument_reference}` : ''}
                      </span>
                      {!notif.is_read ? (
                        <button
                          className="btn-secondary"
                          style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
                          onClick={() => handleMarkNotifRead(notif.id)}
                        >
                          Mark as Read
                        </button>
                      ) : (
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>✓ Read</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* PHASE 4: ADMIN RULES & POLICY MODAL */}
      {isRulesModalOpen && (
        <div className="modal-overlay" onClick={() => setIsRulesModalOpen(false)}>
          <div className="modal-content" style={{ maxWidth: '850px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">⚙️ AICTE Reminder & Escalation SLA Policy Settings</h3>
              <button className="modal-close" onClick={() => setIsRulesModalOpen(false)}>&times;</button>
            </div>

            <div className="tab-nav">
              <button
                className={`tab-btn ${rulesTab === 'reminders' ? 'active' : ''}`}
                onClick={() => setRulesTab('reminders')}
              >
                Maturity Reminder Rules ({reminderRules.length})
              </button>
              <button
                className={`tab-btn ${rulesTab === 'escalations' ? 'active' : ''}`}
                onClick={() => setRulesTab('escalations')}
              >
                Regulatory Escalation Chains ({escalationRules.length})
              </button>
            </div>

            {rulesTab === 'reminders' && (
              <div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                  Configured offsets (in days prior to scheduled FDR maturity) that trigger automated alerts across In-App, Email, and SMS channels.
                </p>
                <table className="portal-table">
                  <thead>
                    <tr>
                      <th>Rule Name</th>
                      <th>Offset Days</th>
                      <th>Channels</th>
                      <th>Target Role</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reminderRules.map(r => (
                      <tr key={r.id}>
                        <td><strong>{r.name}</strong></td>
                        <td><span className="badge-hash">{r.offset_days} Days Before</span></td>
                        <td><span className="notif-channel-pill notif-channel-inapp">{r.channel}</span></td>
                        <td>{r.target_role}</td>
                        <td>
                          <span className={`badge ${r.is_active ? 'badge-confirmed' : 'badge-discrepancy'}`}>
                            {r.is_active ? 'Active' : 'Disabled'}
                          </span>
                        </td>
                        <td>
                          <button
                            className="btn-secondary"
                            style={{ fontSize: '0.72rem', padding: '0.25rem 0.5rem' }}
                            onClick={() => handleToggleReminderRule(r)}
                          >
                            {r.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {rulesTab === 'escalations' && (
              <div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                  Multi-tier escalation ladders that automatically elevate unresolved discrepancies or overdue matured FDRs up the executive hierarchy.
                </p>
                <table className="portal-table">
                  <thead>
                    <tr>
                      <th>Escalation Rule</th>
                      <th>Condition</th>
                      <th>SLA Wait Period</th>
                      <th>Escalation Ladder</th>
                      <th>Status</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {escalationRules.map(e => (
                      <tr key={e.id}>
                        <td><strong>{e.name}</strong></td>
                        <td><span className="badge-hash">{e.trigger_condition}</span></td>
                        <td>{e.wait_period_days} Days Past SLA</td>
                        <td>
                          <span style={{ color: 'var(--accent-saffron)', fontWeight: 600 }}>{e.from_level}</span>
                          {' ➔ '}
                          <span style={{ color: 'var(--accent-rose)', fontWeight: 700 }}>{e.to_level}</span>
                        </td>
                        <td>
                          <span className={`badge ${e.is_active ? 'badge-confirmed' : 'badge-discrepancy'}`}>
                            {e.is_active ? 'Active' : 'Disabled'}
                          </span>
                        </td>
                        <td>
                          <button
                            className="btn-secondary"
                            style={{ fontSize: '0.72rem', padding: '0.25rem 0.5rem' }}
                            onClick={() => handleToggleEscalationRule(e)}
                          >
                            {e.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* SUBMIT FDR MODAL WITH PHASE 3 OCR PRE-FILL */}
      {isSubmitModalOpen && (
        <div className="modal-overlay" onClick={() => setIsSubmitModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Submit New Security Deposit / FDR</h3>
              <button className="modal-close" onClick={() => setIsSubmitModalOpen(false)}>
                &times;
              </button>
            </div>

            {submitError && <div className="alert-box error">{submitError}</div>}
            {submitSuccess && <div className="alert-box success">{submitSuccess}</div>}

            {/* Phase 3 OCR Extractor Dropzone */}
            <div style={{ marginBottom: '1.5rem', background: 'rgba(56, 189, 248, 0.05)', border: '1px dashed rgba(56, 189, 248, 0.3)', borderRadius: '8px', padding: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong style={{ color: '#38bdf8', fontSize: '0.9rem' }}>⚡ Instant OCR Pre-Fill (Optional)</strong>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    Upload your FDR scan to automatically extract Reference Number, Bank Name, Amount, and Dates using OCR.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{ borderColor: 'rgba(56, 189, 248, 0.5)', color: '#38bdf8' }}
                  onClick={() => ocrFileInputRef.current?.click()}
                  disabled={ocrLoading}
                >
                  {ocrLoading ? 'Scanning Scan...' : 'Upload & Scan with OCR'}
                </button>
                <input
                  type="file"
                  ref={ocrFileInputRef}
                  style={{ display: 'none' }}
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={handleOcrFileSelect}
                />
              </div>

              {ocrError && <div className="alert-box error" style={{ marginTop: '0.8rem', padding: '0.5rem' }}>{ocrError}</div>}

              {ocrExtractedData && (
                <div className="ocr-banner" style={{ marginTop: '0.8rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#34d399' }}>
                      ✓ OCR Extraction Succeeded! Review and apply to form:
                    </span>
                    <button
                      type="button"
                      className="btn-primary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.75rem' }}
                      onClick={applyOcrValues}
                    >
                      Apply Extracted Values to Form
                    </button>
                  </div>
                  <div className="ocr-prefill-grid">
                    <div className="ocr-prefill-item">
                      <label>Detected FDR Number</label>
                      <div>{ocrExtractedData.reference_number || 'Not detected'}</div>
                    </div>
                    <div className="ocr-prefill-item">
                      <label>Detected Bank</label>
                      <div>{ocrExtractedData.issuing_bank || 'Not detected'}</div>
                    </div>
                    <div className="ocr-prefill-item">
                      <label>Detected Amount</label>
                      <div>₹{ocrExtractedData.amount ? parseFloat(ocrExtractedData.amount).toLocaleString('en-IN') : 'Not detected'}</div>
                    </div>
                    <div className="ocr-prefill-item">
                      <label>Detected Issue Date</label>
                      <div>{ocrExtractedData.issue_date || 'Not detected'}</div>
                    </div>
                    <div className="ocr-prefill-item">
                      <label>Detected Maturity Date</label>
                      <div>{ocrExtractedData.maturity_date || 'Not detected'}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <form onSubmit={handleSubmitFDR}>
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">FDR Reference Number *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. FDR-SBI-2026-001"
                    value={refNumber}
                    onChange={e => setRefNumber(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Issuing Bank Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. State Bank of India"
                    value={bankName}
                    onChange={e => setBankName(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Issuing Branch Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Connaught Place Branch"
                    value={branchName}
                    onChange={e => setBranchName(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Branch IFSC Code *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. SBIN0000001"
                    maxLength={11}
                    value={ifsc}
                    onChange={e => setIfsc(e.target.value.toUpperCase())}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Principal Amount (INR) *</label>
                  <input
                    type="number"
                    className="form-input"
                    placeholder="e.g. 1500000"
                    step="1000"
                    min="1"
                    value={amount}
                    onChange={e => setAmount(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Deposit Date *</label>
                  <input
                    type="date"
                    className="form-input"
                    value={issueDate}
                    onChange={e => setIssueDate(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Maturity Date *</label>
                  <input
                    type="date"
                    className="form-input"
                    value={maturityDate}
                    onChange={e => setMaturityDate(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Joint Beneficiary Name</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Institution Name and AICTE"
                    value={jointHolder}
                    onChange={e => setJointHolder(e.target.value)}
                  />
                </div>

                {/* Phase 5: Renewal / Replacement Linking Section */}
                <div className="form-group full-width" style={{ background: 'rgba(59, 130, 246, 0.05)', padding: '0.85rem', borderRadius: '6px', border: '1px dashed rgba(59, 130, 246, 0.3)' }}>
                  <label className="form-label" style={{ color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.4rem' }}>
                    <span>🔗 Link to Existing FDR (Renewal / Replacement)</span>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>(Optional)</span>
                  </label>
                  <select
                    className="form-input"
                    value={replacesId}
                    onChange={e => setReplacesId(e.target.value)}
                    style={{ marginBottom: '0.6rem' }}
                  >
                    <option value="">-- None (Standalone Initial Security Deposit) --</option>
                    {instruments.map(inst => (
                      <option key={inst.id} value={inst.id}>
                        {inst.reference_number} • {inst.issuing_bank} (₹{Number(inst.amount || 0).toLocaleString('en-IN')}) [{inst.status}]
                      </option>
                    ))}
                  </select>
                  {replacesId && (
                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Type:</span>
                        <select
                          className="filter-select"
                          value={renewalType}
                          onChange={e => setRenewalType(e.target.value)}
                        >
                          <option value="REPLACEMENT">Replacement (New deposit replaces existing)</option>
                          <option value="RENEWAL">Renewal (Maturity rollover / extension)</option>
                        </select>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#93c5fd', fontStyle: 'italic' }}>
                        ⚡ Automated Chaining: When this new instrument is verified by the officer, the linked FDR will automatically transition to 'Replaced' and maintain full lineage history.
                      </div>
                    </div>
                  )}
                </div>

                <div className="form-group full-width">
                  <label className="form-checkbox-label">
                    <input
                      type="checkbox"
                      checked={lienMarked}
                      onChange={e => setLienMarked(e.target.checked)}
                    />
                    <span>Lien has been officially marked in favor of Member Secretary, AICTE</span>
                  </label>
                </div>

                {/* Upload File Section */}
                <div className="form-group full-width">
                  <label className="form-label">FDR Certificate Scanned Document (Encrypted at Rest)</label>
                  <div
                    className="dropzone"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <div className="dropzone-icon">📄</div>
                    <div className="dropzone-text">
                      {selectedFile ? selectedFile.name : 'Click to select FDR certificate (PDF, JPG, PNG)'}
                    </div>
                    <div className="dropzone-subtext">
                      Maximum 15 MB • Encrypted with Fernet key at rest outside web root
                    </div>
                  </div>
                  <input
                    type="file"
                    ref={fileInputRef}
                    style={{ display: 'none' }}
                    accept=".pdf,.jpg,.jpeg,.png"
                    onChange={handleFileChange}
                  />

                  {selectedFile && fileHashPreview && (
                    <div className="file-preview-card">
                      <div>
                        <strong>{selectedFile.name}</strong> ({(selectedFile.size / 1024).toFixed(1)} KB)
                        <div style={{ marginTop: '0.2rem' }}>
                          <span className="badge-hash">SHA-256: {fileHashPreview}</span>
                        </div>
                      </div>
                      <span className="badge badge-confirmed">Validated</span>
                    </div>
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.8rem' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setIsSubmitModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Encrypting & Saving...' : 'Submit FDR'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* INSTRUMENT DETAIL & VAULT MODAL */}
      {selectedInstrument && (
        <div className="modal-overlay" onClick={() => setSelectedInstrument(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">{selectedInstrument.reference_number}</h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  {selectedInstrument.institution_name} • {selectedInstrument.issuing_bank} (IFSC: {selectedInstrument.branch_ifsc})
                </p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                <span className={`badge badge-status-${selectedInstrument.status.toLowerCase().replace(' ', '-')}`}>
                  {selectedInstrument.status}
                </span>
                <button className="modal-close" onClick={() => setSelectedInstrument(null)}>
                  &times;
                </button>
              </div>
            </div>

            {/* MOCK BANK SANDBOX BANNER */}
            <div className="mock-bank-banner">
              <span className="mock-bank-tag">MOCK API SANDBOX</span>
              <div>
                <div>
                  Running with <strong>MockBankAdapter</strong>. Simulates core banking query with seeded edge-case registries.
                </div>
                <div style={{ marginTop: '0.35rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Quick Test References: </span>
                  <span className="seed-chip" onClick={() => handleBankVerify(selectedInstrument.id)}>
                    Click to Verify Current
                  </span>
                  <span className="seed-chip" title="Match">FDR-SBI-2026-001 (Match)</span>
                  <span className="seed-chip" title="Amount Mismatch">FDR-PNB-MISMATCH-AMT</span>
                  <span className="seed-chip" title="Date Mismatch">FDR-HDFC-MISMATCH-DATE</span>
                  <span className="seed-chip" title="Not Found">FDR-UNKNOWN-404</span>
                </div>
              </div>
            </div>

            {/* TRUST SCORE GAUGE */}
            <div className="trust-meter-card">
              <div className="trust-score-gauge">
                <div
                  className="trust-score-num"
                  style={{
                    color:
                      selectedInstrument.trust_score >= 80
                        ? 'var(--accent-emerald)'
                        : selectedInstrument.trust_score >= 50
                        ? 'var(--accent-saffron)'
                        : 'var(--accent-rose)',
                  }}
                >
                  {selectedInstrument.trust_score}
                  <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>/100</span>
                </div>
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff' }}>Instrument Trust Score</div>
                  <div className="trust-bar-bg">
                    <div
                      className="trust-bar-fill"
                      style={{
                        width: `${selectedInstrument.trust_score}%`,
                        background:
                          selectedInstrument.trust_score >= 80
                            ? 'var(--accent-emerald)'
                            : selectedInstrument.trust_score >= 50
                            ? 'var(--accent-saffron)'
                            : 'var(--accent-rose)',
                      }}
                    ></div>
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    Calculated from CBS confirmation (40%), discrepancy health (40%), and vault completeness (20%).
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.6rem' }}>
                <span
                  className={`badge ${
                    selectedInstrument.claimed_vs_confirmed?.amount?.confirmed ? 'badge-confirmed' : 'badge-discrepancy'
                  }`}
                >
                  {selectedInstrument.claimed_vs_confirmed?.amount?.confirmed ? '✓ CBS Confirmed' : 'Pending CBS'}
                </span>
                <span
                  className={`badge ${
                    selectedInstrument.discrepancies?.filter(d => !d.is_resolved).length === 0
                      ? 'badge-confirmed'
                      : 'badge-discrepancy'
                  }`}
                >
                  {selectedInstrument.discrepancies?.filter(d => !d.is_resolved).length === 0
                    ? '0 Open Flags'
                    : `${selectedInstrument.discrepancies?.filter(d => !d.is_resolved).length} Flags Active`}
                </span>
              </div>
            </div>

            {/* TAB NAVIGATION */}
            <div className="tab-nav">
              <button
                className={`tab-btn ${modalTab === 'overview' ? 'active' : ''}`}
                onClick={() => setModalTab('overview')}
              >
                Overview & Scrutiny
              </button>
              <button
                className={`tab-btn ${modalTab === 'discrepancies' ? 'active' : ''}`}
                onClick={() => setModalTab('discrepancies')}
              >
                Discrepancy Engine ({selectedInstrument.discrepancies?.length || 0})
              </button>
              <button
                className={`tab-btn ${modalTab === 'documents' ? 'active' : ''}`}
                onClick={() => setModalTab('documents')}
              >
                Encrypted Vault ({selectedInstrument.documents?.length || 0})
              </button>
              <button
                className={`tab-btn ${modalTab === 'remarks' ? 'active' : ''}`}
                onClick={() => setModalTab('remarks')}
              >
                Audit Timeline ({selectedInstrument.remarks?.length || 0})
              </button>
              <button
                className={`tab-btn ${modalTab === 'lineage' ? 'active' : ''}`}
                onClick={() => setModalTab('lineage')}
              >
                ⛓️ Lineage Timeline ({selectedInstrument.replacement_chain?.length || 1})
              </button>
              <button
                className={`tab-btn ${modalTab === 'release' ? 'active' : ''}`}
                onClick={() => setModalTab('release')}
              >
                🏛️ Release & Refund
              </button>
            </div>

            {/* TAB 1: OVERVIEW & SCRUTINY */}
            {modalTab === 'overview' && (
              <div>
                {/* Officer Scrutiny Console Actions */}
                {(USERS[currentUserIdx].role === 'SCRUTINY_OFFICER' || USERS[currentUserIdx].role === 'ADMIN') && (
                  <div
                    style={{
                      background: 'rgba(15, 23, 42, 0.7)',
                      padding: '1rem',
                      borderRadius: '8px',
                      border: '1px solid var(--border-color)',
                      marginBottom: '1.5rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: '0.8rem',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff' }}>
                        Officer Scrutiny & CBS Verification Console
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Trigger automated CBS reconciliation or flag manual discrepancies for this instrument.
                      </div>
                      <div style={{ marginTop: '0.4rem' }}>
                        <input
                          type="text"
                          className="form-input"
                          style={{ fontSize: '0.75rem', padding: '0.35rem 0.6rem', width: '280px' }}
                          placeholder="Verification note..."
                          value={verifyNotes}
                          onChange={e => setVerifyNotes(e.target.value)}
                        />
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center' }}>
                      <button
                        className="btn-primary"
                        onClick={() => handleBankVerify(selectedInstrument.id)}
                        disabled={isVerifying}
                      >
                        {isVerifying ? 'Querying CBS [MOCK]...' : '⚡ Verify with Bank [MOCK]'}
                      </button>
                      <button
                        className="btn-secondary"
                        style={{ color: 'var(--accent-rose)', borderColor: 'rgba(244, 63, 94, 0.4)' }}
                        onClick={() => setIsFlagModalOpen(true)}
                      >
                        ⚠️ Flag Discrepancy
                      </button>
                      <button
                        className="btn-secondary"
                        style={{ color: 'var(--accent-emerald)', borderColor: 'rgba(16, 185, 129, 0.4)' }}
                        onClick={() => handleMarkVerified(selectedInstrument.id)}
                      >
                        ✓ Mark Verified
                      </button>
                    </div>
                  </div>
                )}

                {/* Claimed vs Bank-Confirmed Reconciliation Table */}
                <div style={{ marginBottom: '1.5rem', background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--accent-saffron)', marginBottom: '0.6rem' }}>
                    Claimed vs Bank-Confirmed Reconciliation (Field Provenance)
                  </h4>
                  <table className="portal-table" style={{ background: 'transparent' }}>
                    <thead>
                      <tr>
                        <th>Field Name</th>
                        <th>Institution Claimed Value</th>
                        <th>CBS Confirmed Value</th>
                        <th>Provenance Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><strong>Principal Deposit Amount</strong></td>
                        <td>
                          <span className="badge badge-claimed">
                            ₹{parseFloat(selectedInstrument.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </span>
                        </td>
                        <td>
                          {selectedInstrument.claimed_vs_confirmed?.amount?.confirmed ? (
                            <span className="badge badge-confirmed">
                              ₹{parseFloat(selectedInstrument.claimed_vs_confirmed.amount.confirmed.value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>Pending Bank Scrutiny</span>
                          )}
                        </td>
                        <td>
                          {selectedInstrument.claimed_vs_confirmed?.amount?.confirmed ? (
                            selectedInstrument.claimed_vs_confirmed.amount.claimed.value === selectedInstrument.claimed_vs_confirmed.amount.confirmed.value ? (
                              <span className="badge badge-confirmed">✓ Exact Match</span>
                            ) : (
                              <span className="badge badge-discrepancy">⚠ Mismatch Flagged</span>
                            )
                          ) : (
                            <span className="badge badge-claimed">Institution Only</span>
                          )}
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Maturity Date</strong></td>
                        <td><span className="badge badge-claimed">{selectedInstrument.maturity_date}</span></td>
                        <td>
                          {selectedInstrument.claimed_vs_confirmed?.maturity_date?.confirmed ? (
                            <span className="badge badge-confirmed">
                              {selectedInstrument.claimed_vs_confirmed.maturity_date.confirmed.value}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>Pending Bank Scrutiny</span>
                          )}
                        </td>
                        <td>
                          {selectedInstrument.claimed_vs_confirmed?.maturity_date?.confirmed ? (
                            selectedInstrument.claimed_vs_confirmed.maturity_date.claimed.value === selectedInstrument.claimed_vs_confirmed.maturity_date.confirmed.value ? (
                              <span className="badge badge-confirmed">✓ Exact Match</span>
                            ) : (
                              <span className="badge badge-discrepancy">⚠ Mismatch Flagged</span>
                            )
                          ) : (
                            <span className="badge badge-claimed">Institution Only</span>
                          )}
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Deposit / Issue Date</strong></td>
                        <td><span className="badge badge-claimed">{selectedInstrument.issue_date}</span></td>
                        <td>
                          {selectedInstrument.claimed_vs_confirmed?.issue_date?.confirmed ? (
                            <span className="badge badge-confirmed">
                              {selectedInstrument.claimed_vs_confirmed.issue_date.confirmed.value}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>Pending Bank Scrutiny</span>
                          )}
                        </td>
                        <td>
                          {selectedInstrument.claimed_vs_confirmed?.issue_date?.confirmed ? (
                            <span className="badge badge-confirmed">✓ Confirmed</span>
                          ) : (
                            <span className="badge badge-claimed">Institution Only</span>
                          )}
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Lien in Favor of AICTE</strong></td>
                        <td>
                          {selectedInstrument.lien_in_favour_of_aicte ? (
                            <span className="badge badge-claimed">Declared Yes</span>
                          ) : (
                            <span className="badge badge-discrepancy">Declared No</span>
                          )}
                        </td>
                        <td>
                          {selectedInstrument.claimed_vs_confirmed?.lien_in_favour_of_aicte?.confirmed ? (
                            selectedInstrument.claimed_vs_confirmed.lien_in_favour_of_aicte.confirmed.value === 'True' ||
                            selectedInstrument.claimed_vs_confirmed.lien_in_favour_of_aicte.confirmed.value === 'true' ? (
                              <span className="badge badge-confirmed">✓ Lien Active in CBS</span>
                            ) : (
                              <span className="badge badge-discrepancy">⚠ Lien Not Marked in CBS</span>
                            )
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>Pending Bank Scrutiny</span>
                          )}
                        </td>
                        <td>
                          {selectedInstrument.claimed_vs_confirmed?.lien_in_favour_of_aicte?.confirmed ? (
                            <span className="badge badge-confirmed">Bank Verified</span>
                          ) : (
                            <span className="badge badge-claimed">Institution Only</span>
                          )}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Simulated CBS Bank Payload Inspector */}
                {lastBankResult && (
                  <div style={{ marginTop: '1rem', background: 'rgba(0,0,0,0.4)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8' }}>
                        Latest Mock CBS Verification Response Payload
                      </span>
                      <span className="badge-hash">Ref: {lastBankResult.bank_reference_id}</span>
                    </div>
                    <pre style={{ fontSize: '0.75rem', color: '#94a3b8', overflowX: 'auto', maxHeight: '180px' }}>
                      {JSON.stringify(lastBankResult, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: DISCREPANCIES */}
            {modalTab === 'discrepancies' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h4 style={{ fontSize: '0.95rem', color: '#fff' }}>
                    Rule-Based Discrepancy Engine Diagnostics
                  </h4>
                  {(USERS[currentUserIdx].role === 'SCRUTINY_OFFICER' || USERS[currentUserIdx].role === 'ADMIN') && (
                    <button
                      className="btn-secondary"
                      style={{ color: 'var(--accent-rose)', borderColor: 'rgba(244, 63, 94, 0.4)', fontSize: '0.78rem' }}
                      onClick={() => setIsFlagModalOpen(true)}
                    >
                      + Flag Manual Issue
                    </button>
                  )}
                </div>

                {selectedInstrument.discrepancies?.length === 0 ? (
                  <div style={{ padding: '2rem', background: 'rgba(16, 185, 129, 0.05)', borderRadius: '8px', textAlign: 'center', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                    <div style={{ fontSize: '1.2rem', color: 'var(--accent-emerald)', marginBottom: '0.3rem' }}>✓ Clean Integrity Record</div>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      No rule discrepancies or mismatch flags have been detected on this instrument.
                    </p>
                  </div>
                ) : (
                  <div>
                    {selectedInstrument.discrepancies?.map(disc => (
                      <div
                        key={disc.id}
                        className={`discrepancy-card sev-${disc.severity.toLowerCase()} ${disc.is_resolved ? 'is-resolved' : ''}`}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span className={`sev-badge sev-badge-${disc.severity.toLowerCase()}`}>
                                {disc.severity}
                              </span>
                              <strong style={{ color: '#fff', fontSize: '0.88rem' }}>{disc.title}</strong>
                              <span className="badge-hash">{disc.rule_code}</span>
                            </div>
                            <div style={{ fontSize: '0.82rem', color: '#f1f5f9', marginTop: '0.35rem' }}>
                              {disc.description}
                            </div>
                            {disc.details && Object.keys(disc.details).length > 0 && (
                              <div style={{ marginTop: '0.4rem', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                                Details: <code>{JSON.stringify(disc.details)}</code>
                              </div>
                            )}
                          </div>

                          <div>
                            {disc.is_resolved ? (
                              <div style={{ textAlign: 'right' }}>
                                <span className="badge badge-confirmed">✓ Resolved</span>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                                  By {disc.resolved_by_username || 'Officer'} on {disc.resolved_at ? new Date(disc.resolved_at).toLocaleDateString() : ''}
                                </div>
                                {disc.resolution_note && (
                                  <div style={{ fontSize: '0.72rem', color: '#94a3b8', fontStyle: 'italic', marginTop: '0.15rem' }}>
                                    "{disc.resolution_note}"
                                  </div>
                                )}
                              </div>
                            ) : (
                              (USERS[currentUserIdx].role === 'SCRUTINY_OFFICER' || USERS[currentUserIdx].role === 'ADMIN') && (
                                <button
                                  className="btn-secondary"
                                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.7rem', color: 'var(--accent-emerald)', borderColor: 'rgba(16, 185, 129, 0.4)' }}
                                  onClick={() => {
                                    setResolvingDiscrepancy(disc);
                                    setResolutionNote('');
                                  }}
                                >
                                  Resolve Issue
                                </button>
                              )
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: ENCRYPTED VAULT */}
            {modalTab === 'documents' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h4 style={{ fontSize: '0.95rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span>Encrypted Document Vault & Version History</span>
                    <span className="badge badge-confirmed" style={{ fontSize: '0.65rem' }}>FERNET AT REST</span>
                  </h4>
                </div>

                {selectedInstrument.documents?.length === 0 ? (
                  <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No documents in vault yet.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                    {selectedInstrument.documents?.map(doc => (
                      <div
                        key={doc.id}
                        style={{
                          padding: '0.85rem 1rem',
                          background: 'rgba(255,255,255,0.03)',
                          borderRadius: '6px',
                          border: '1px solid var(--border-color)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          flexWrap: 'wrap',
                          gap: '0.5rem',
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span className="badge badge-version">v{doc.version}</span>
                            <strong style={{ color: '#fff', fontSize: '0.85rem' }}>{doc.file_name}</strong>
                            {doc.is_current_version ? (
                              <span className="badge badge-confirmed">Current</span>
                            ) : (
                              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>(Superseded)</span>
                            )}
                            {doc.is_duplicate_hash && (
                              <span className="badge badge-duplicate-alert">
                                Duplicate Hash Re-use Detected!
                              </span>
                            )}
                          </div>
                          <div style={{ marginTop: '0.35rem', display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
                            <span className="badge-hash">SHA-256: {doc.sha256_hash.slice(0, 16)}...</span>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              {(doc.file_size_bytes / 1024).toFixed(1)} KB • Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}
                            </span>
                          </div>
                          {doc.is_duplicate_hash && doc.duplicate_of_reference && (
                            <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', color: 'var(--accent-rose)' }}>
                              * Warning: Identical fingerprint previously uploaded under instrument <strong>{doc.duplicate_of_reference}</strong>.
                            </div>
                          )}
                        </div>

                        <button
                          className="btn-secondary"
                          style={{ fontSize: '0.78rem', padding: '0.4rem 0.8rem' }}
                          onClick={() => handleSecureDownload(doc)}
                        >
                          Download Decrypted
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Upload New Version Widget */}
                <div style={{ marginTop: '1.25rem', padding: '1rem', background: 'rgba(15,23,42,0.8)', borderRadius: '8px', border: '1px dashed var(--border-color)' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                    Upload New Document Version
                  </div>
                  {versionUploadError && <div className="alert-box error" style={{ padding: '0.5rem' }}>{versionUploadError}</div>}
                  <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <select
                      className="filter-select"
                      value={versionDocType}
                      onChange={e => setVersionDocType(e.target.value)}
                    >
                      <option value="FDR_CERTIFICATE">FDR Certificate</option>
                      <option value="BANK_CONFIRMATION">Bank Confirmation Letter</option>
                      <option value="JOINT_PLEDGE_DEED">Joint Pledge Deed</option>
                      <option value="NOC_DOCUMENT">NOC Document</option>
                      <option value="OTHER">Other</option>
                    </select>

                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={e => setVersionFile(e.target.files?.[0] || null)}
                    />

                    <button
                      className="btn-primary"
                      disabled={!versionFile || uploadingVersion}
                      onClick={handleUploadNewVersion}
                    >
                      {uploadingVersion ? 'Encrypting...' : 'Upload Version'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: REMARKS & AUDIT */}
            {modalTab === 'remarks' && (
              <div>
                <h4 style={{ fontSize: '0.9rem', color: '#fff', marginBottom: '0.8rem' }}>
                  Scrutiny Observations & Remarks Timeline
                </h4>
                {selectedInstrument.remarks?.length === 0 ? (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No remarks recorded yet.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
                    {selectedInstrument.remarks?.map(rem => (
                      <div
                        key={rem.id}
                        style={{
                          padding: '0.6rem 0.85rem',
                          background: rem.remark_type === 'DISCREPANCY_FLAG' ? 'rgba(244,63,94,0.1)' : 'rgba(255,255,255,0.02)',
                          borderLeft: rem.remark_type === 'DISCREPANCY_FLAG' ? '3px solid var(--accent-rose)' : '3px solid var(--accent-blue)',
                          borderRadius: '4px',
                          fontSize: '0.8rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                          <span>{rem.author_username} ({rem.role}) • {rem.remark_type}</span>
                          <span>{new Date(rem.created_at).toLocaleString()}</span>
                        </div>
                        <div style={{ marginTop: '0.3rem', color: '#f8fafc' }}>{rem.text}</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add Remark Form */}
                <div style={{ background: 'rgba(15,23,42,0.8)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                    Post New Scrutiny Remark
                  </div>
                  <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '0.6rem' }}>
                    <select
                      className="filter-select"
                      value={newRemarkType}
                      onChange={e => setNewRemarkType(e.target.value)}
                    >
                      <option value="SCRUTINY_NOTE">Scrutiny Note</option>
                      <option value="CLARIFICATION_REQUEST">Clarification Request</option>
                      <option value="DISCREPANCY_FLAG">Discrepancy Flag</option>
                      <option value="APPROVAL_NOTE">Approval Note</option>
                    </select>
                  </div>
                  <textarea
                    className="form-textarea"
                    rows={2}
                    placeholder="Enter observation or remark..."
                    value={newRemarkText}
                    onChange={e => setNewRemarkText(e.target.value)}
                    style={{ width: '100%', marginBottom: '0.6rem' }}
                  ></textarea>
                  <button
                    className="btn-primary"
                    disabled={!newRemarkText || isSubmittingRemark}
                    onClick={handleAddRemark}
                  >
                    {isSubmittingRemark ? 'Posting...' : 'Post Remark'}
                  </button>
                </div>
              </div>
            )}

            {/* TAB 5: REPLACEMENT & RENEWAL LINEAGE TIMELINE */}
            {modalTab === 'lineage' && (
              <div className="lineage-timeline-wrapper">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                  <div>
                    <h4 style={{ fontSize: '1rem', color: '#fff', margin: 0 }}>
                      Deposit Renewal & Replacement History
                    </h4>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '0.2rem 0 0' }}>
                      Complete chronological chain of instruments showing initial deposit and all successive replacements.
                    </p>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--accent-saffron)', background: 'rgba(245,158,11,0.1)', padding: '0.3rem 0.65rem', borderRadius: '4px', border: '1px solid rgba(245,158,11,0.3)' }}>
                    Chain Length: {selectedInstrument.replacement_chain?.length || 1} Instruments
                  </div>
                </div>

                <div className="lineage-timeline">
                  {((selectedInstrument.replacement_chain && selectedInstrument.replacement_chain.length > 0)
                    ? selectedInstrument.replacement_chain
                    : [{
                        id: selectedInstrument.id,
                        reference_number: selectedInstrument.reference_number,
                        issuing_bank: selectedInstrument.issuing_bank,
                        amount: selectedInstrument.amount,
                        issue_date: selectedInstrument.issue_date,
                        maturity_date: selectedInstrument.maturity_date,
                        status: selectedInstrument.status,
                        renewal_type: selectedInstrument.renewal_type || null,
                        replaces_id: selectedInstrument.replaces || null,
                        generation: 1,
                        is_current: true,
                        created_at: selectedInstrument.created_at,
                      }]
                  ).map((node, index, arr) => {
                    const isSelected = node.id === selectedInstrument.id;
                    const isLast = index === arr.length - 1;
                    return (
                      <div key={node.id} className={`timeline-node-card ${isSelected ? 'current' : ''}`}>
                        <div className="timeline-track-col">
                          <div className={`timeline-dot ${isSelected ? 'current' : node.status === 'Replaced' ? 'replaced' : ''}`}>
                            {node.generation || index + 1}
                          </div>
                          {!isLast && <div className="timeline-line"></div>}
                        </div>
                        <div className="timeline-details">
                          <div className="timeline-title-row">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                              <span className="timeline-ref">{node.reference_number}</span>
                              <span className={`status-badge status-${node.status.toLowerCase().replace(/\s+/g, '-')}`}>
                                {node.status}
                              </span>
                              {isSelected && (
                                <span style={{ fontSize: '0.68rem', background: 'var(--accent-saffron)', color: '#000', fontWeight: 800, padding: '0.1rem 0.45rem', borderRadius: '3px' }}>
                                  CURRENT VIEW
                                </span>
                              )}
                              {node.renewal_type && (
                                <span style={{ fontSize: '0.68rem', background: 'rgba(59,130,246,0.2)', color: '#93c5fd', padding: '0.1rem 0.45rem', borderRadius: '3px', border: '1px solid rgba(59,130,246,0.3)' }}>
                                  {node.renewal_type}
                                </span>
                              )}
                            </div>
                            {!isSelected && (
                              <button
                                className="btn-secondary"
                                style={{ padding: '0.25rem 0.65rem', fontSize: '0.72rem' }}
                                onClick={() => refreshSingleInstrument(node.id)}
                              >
                                View Details ↗
                              </button>
                            )}
                          </div>

                          <div className="timeline-meta-grid">
                            <div>
                              <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Bank & Branch</div>
                              <div style={{ color: '#fff', fontWeight: 600 }}>{node.issuing_bank}</div>
                            </div>
                            <div>
                              <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Principal Amount</div>
                              <div style={{ color: 'var(--accent-emerald)', fontWeight: 700 }}>
                                ₹{Number(node.amount || 0).toLocaleString('en-IN')}
                              </div>
                            </div>
                            <div>
                              <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Deposit Date</div>
                              <div style={{ color: '#e2e8f0' }}>{node.issue_date}</div>
                            </div>
                            <div>
                              <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Maturity Date</div>
                              <div style={{ color: '#e2e8f0' }}>{node.maturity_date}</div>
                            </div>
                          </div>

                          {node.status === 'Replaced' && (
                            <div style={{ marginTop: '0.6rem', fontSize: '0.73rem', color: '#94a3b8', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                              <span>🔄</span> Replaced in AICTE records by subsequent verified instrument.
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* TAB 6: RELEASE & REFUND WORKFLOW CONSOLE */}
            {modalTab === 'release' && (
              <div>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.2rem' }}>
                  <div>
                    <h4 style={{ fontSize: '1rem', color: '#fff', margin: 0 }}>
                      AICTE Security Deposit Release & Refund Workflow
                    </h4>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '0.2rem 0 0' }}>
                      Enforced 4-stage lifecycle: Request → Scrutiny → Approver Sanction → Release.
                    </p>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span className={`status-badge status-${selectedInstrument.status.toLowerCase().replace(/\s+/g, '-')}`} style={{ fontSize: '0.85rem' }}>
                      Status: {selectedInstrument.status}
                    </span>
                    {selectedInstrument.compliance_hold && (
                      <div style={{ marginTop: '0.35rem' }}>
                        <span style={{ background: '#ef4444', color: '#fff', fontSize: '0.68rem', fontWeight: 800, padding: '0.15rem 0.5rem', borderRadius: '4px' }}>
                          ⛔ COMPLIANCE HOLD ACTIVE
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Preconditions Checklist Cards */}
                <div style={{ marginBottom: '1.25rem' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.65rem' }}>
                    Automated Statutory Preconditions Checklist
                  </div>
                  <div className="checklist-grid">
                    {/* 1. Bank Verification */}
                    <div className={`checklist-card ${selectedInstrument.release_checklist?.is_bank_confirmed ? 'pass' : 'fail'}`}>
                      <div className="checklist-header">
                        <span className="checklist-title">1. CBS Bank-Verified</span>
                        <span className={`checklist-status-pill ${selectedInstrument.release_checklist?.is_bank_confirmed ? 'pass' : 'fail'}`}>
                          {selectedInstrument.release_checklist?.is_bank_confirmed ? 'PASSED' : 'FAILED'}
                        </span>
                      </div>
                      <div className="checklist-desc">
                        {selectedInstrument.release_checklist?.is_bank_confirmed
                          ? 'Instrument confirmed authentic by Core Banking System adapter.'
                          : 'Deposit not verified by issuing bank CBS adapter.'}
                      </div>
                    </div>

                    {/* 2. Zero Discrepancies */}
                    <div className={`checklist-card ${selectedInstrument.release_checklist?.no_open_discrepancies ? 'pass' : 'fail'}`}>
                      <div className="checklist-header">
                        <span className="checklist-title">2. Discrepancies Clean</span>
                        <span className={`checklist-status-pill ${selectedInstrument.release_checklist?.no_open_discrepancies ? 'pass' : 'fail'}`}>
                          {selectedInstrument.release_checklist?.no_open_discrepancies ? 'PASSED' : 'FAILED'}
                        </span>
                      </div>
                      <div className="checklist-desc">
                        {selectedInstrument.release_checklist?.no_open_discrepancies
                          ? 'Zero unresolved flags in the discrepancy detection engine.'
                          : `${selectedInstrument.discrepancies?.filter(d => !d.is_resolved).length || 0} unresolved discrepancy flags detected.`}
                      </div>
                    </div>

                    {/* 3. Lock-in Tenure or NOC */}
                    <div className={`checklist-card ${selectedInstrument.release_checklist?.lock_in_satisfied ? 'pass' : 'warn'}`}>
                      <div className="checklist-header">
                        <span className="checklist-title">3. Lock-in / NOC</span>
                        <span className={`checklist-status-pill ${selectedInstrument.release_checklist?.lock_in_satisfied ? 'pass' : 'warn'}`}>
                          {selectedInstrument.release_checklist?.lock_in_satisfied ? 'PASSED' : 'PENDING'}
                        </span>
                      </div>
                      <div className="checklist-desc">
                        {selectedInstrument.release_checklist?.lock_in_satisfied
                          ? '8-year statutory lock-in completed or official NOC satisfied.'
                          : 'Within mandatory 8-year lock-in period; requires Council NOC.'}
                      </div>
                    </div>

                    {/* 4. Compliance Hold Status */}
                    <div className={`checklist-card ${selectedInstrument.release_checklist?.no_compliance_hold ? 'pass' : 'fail'}`}>
                      <div className="checklist-header">
                        <span className="checklist-title">4. Compliance Hold</span>
                        <span className={`checklist-status-pill ${selectedInstrument.release_checklist?.no_compliance_hold ? 'pass' : 'fail'}`}>
                          {selectedInstrument.release_checklist?.no_compliance_hold ? 'CLEARED' : 'BLOCKED'}
                        </span>
                      </div>
                      <div className="checklist-desc">
                        {selectedInstrument.release_checklist?.no_compliance_hold
                          ? 'No pending regulatory, CBI, or court compliance holds.'
                          : `Hold Active: ${selectedInstrument.compliance_hold_reason || 'Pending inquiry'}`}
                      </div>
                    </div>

                    {/* 5. Mandatory Documents */}
                    <div className={`checklist-card ${selectedInstrument.release_checklist?.has_required_documents ? 'pass' : 'fail'}`}>
                      <div className="checklist-header">
                        <span className="checklist-title">5. Vault Certificates</span>
                        <span className={`checklist-status-pill ${selectedInstrument.release_checklist?.has_required_documents ? 'pass' : 'fail'}`}>
                          {selectedInstrument.release_checklist?.has_required_documents ? 'PRESENT' : 'MISSING'}
                        </span>
                      </div>
                      <div className="checklist-desc">
                        {selectedInstrument.release_checklist?.has_required_documents
                          ? 'Mandatory FDR certificate encrypted and verified in storage.'
                          : 'Mandatory certificate documents not found in secure vault.'}
                      </div>
                    </div>
                  </div>

                  {/* Overall Gate Summary Banner */}
                  <div
                    style={{
                      padding: '0.85rem 1rem',
                      borderRadius: '6px',
                      background: selectedInstrument.release_checklist?.all_conditions_met ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                      border: `1px solid ${selectedInstrument.release_checklist?.all_conditions_met ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <span style={{ fontSize: '1.2rem' }}>
                        {selectedInstrument.release_checklist?.all_conditions_met ? '✅' : '⛔'}
                      </span>
                      <div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 700, color: selectedInstrument.release_checklist?.all_conditions_met ? '#34d399' : '#f87171' }}>
                          {selectedInstrument.release_checklist?.all_conditions_met
                            ? 'All Statutory Preconditions Satisfied — Eligible for Release Sanction'
                            : 'Release Gate Blocked — Statutory Preconditions Not Met'}
                        </div>
                        <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                          {selectedInstrument.release_checklist?.all_conditions_met
                            ? 'The Approving Authority can formally sign and release the security deposit.'
                            : 'All 5 preconditions must be met before sanction order can be executed.'}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Audit & Workflow Milestones Timeline */}
                <div style={{ background: 'rgba(0,0,0,0.25)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)', marginBottom: '1.25rem' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.6rem' }}>
                    Workflow Milestone Audit History
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.8rem', fontSize: '0.78rem' }}>
                    <div>
                      <div style={{ color: 'var(--text-muted)' }}>1. Release Requested</div>
                      <div style={{ color: '#fff', fontWeight: 600 }}>
                        {selectedInstrument.release_requested_at ? new Date(selectedInstrument.release_requested_at).toLocaleString() : 'Not Yet Requested'}
                      </div>
                      {selectedInstrument.release_justification && (
                        <div style={{ color: '#94a3b8', fontSize: '0.72rem', marginTop: '0.2rem' }}>
                          "{selectedInstrument.release_justification}"
                        </div>
                      )}
                    </div>
                    <div>
                      <div style={{ color: 'var(--text-muted)' }}>2. Officer Scrutiny</div>
                      <div style={{ color: '#fff', fontWeight: 600 }}>
                        {selectedInstrument.scrutiny_recommended_at ? new Date(selectedInstrument.scrutiny_recommended_at).toLocaleString() : 'Pending Scrutiny'}
                      </div>
                      {selectedInstrument.scrutiny_recommendation && (
                        <div style={{ color: '#38bdf8', fontSize: '0.72rem', marginTop: '0.2rem' }}>
                          {selectedInstrument.scrutiny_recommendation} • {selectedInstrument.scrutiny_notes}
                        </div>
                      )}
                    </div>
                    <div>
                      <div style={{ color: 'var(--text-muted)' }}>3. Final Sanction / Release</div>
                      <div style={{ color: '#fff', fontWeight: 600 }}>
                        {selectedInstrument.released_at ? new Date(selectedInstrument.released_at).toLocaleString() : 'Pending Sanction'}
                      </div>
                      {selectedInstrument.release_order_reference && (
                        <div style={{ color: '#34d399', fontSize: '0.72rem', marginTop: '0.2rem' }}>
                          Order Ref: {selectedInstrument.release_order_reference}
                        </div>
                      )}
                      {selectedInstrument.rejection_reason && (
                        <div style={{ color: '#fb7185', fontSize: '0.72rem', marginTop: '0.2rem' }}>
                          Rejection Reason: {selectedInstrument.rejection_reason}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Release Feedback Messages */}
                {releaseActionSuccess && (
                  <div style={{ padding: '0.75rem', background: 'rgba(16,185,129,0.15)', border: '1px solid #10b981', color: '#34d399', borderRadius: '6px', fontSize: '0.8rem', marginBottom: '1rem' }}>
                    ✓ {releaseActionSuccess}
                  </div>
                )}
                {releaseActionError && (
                  <div style={{ padding: '0.75rem', background: 'rgba(239,68,68,0.15)', border: '1px solid #ef4444', color: '#f87171', borderRadius: '6px', fontSize: '0.8rem', marginBottom: '1rem' }}>
                    ⚠️ {releaseActionError}
                  </div>
                )}

                {/* ROLE-SPECIFIC ACTION PANELS */}

                {/* 1. Institution Panel */}
                {USERS[currentUserIdx].role === 'INSTITUTION' && (
                  <div className="release-action-panel">
                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff', marginBottom: '0.5rem' }}>
                      Institution Release & Refund Application
                    </div>
                    {selectedInstrument.status === 'Released' ? (
                      <div style={{ color: '#34d399', fontSize: '0.82rem' }}>
                        🎉 Deposit successfully released! Refund has been processed to your registered institution account.
                      </div>
                    ) : selectedInstrument.status === 'Release Requested' ? (
                      <div style={{ color: '#38bdf8', fontSize: '0.82rem' }}>
                        ⏳ Release application submitted on {new Date(selectedInstrument.release_requested_at || '').toLocaleDateString()}. Currently under review by AICTE Scrutiny Officers.
                      </div>
                    ) : selectedInstrument.status === 'Replaced' ? (
                      <div style={{ color: '#94a3b8', fontSize: '0.82rem' }}>
                        This instrument has already been replaced by a subsequent deposit. Release must be requested for the active replacement instrument.
                      </div>
                    ) : (
                      <div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.8rem' }}>
                          Submit an official request to AICTE Regulation Bureau for deposit release and refund.
                        </div>
                        <textarea
                          className="form-textarea"
                          rows={2}
                          placeholder="Provide justification (e.g., Completion of 8-year lock-in period / AICTE Closure Approval NOC reference)..."
                          value={releaseJustification}
                          onChange={e => setReleaseJustification(e.target.value)}
                          style={{ width: '100%', marginBottom: '0.8rem' }}
                        />
                        <button
                          className="btn-primary"
                          disabled={isRequestingRelease || !releaseJustification.trim()}
                          onClick={handleRequestRelease}
                        >
                          {isRequestingRelease ? 'Submitting Application...' : 'Submit Release Application'}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* 2. Scrutiny Officer Panel */}
                {(USERS[currentUserIdx].role === 'SCRUTINY_OFFICER' || USERS[currentUserIdx].role === 'ADMIN') && (
                  <div className="release-action-panel">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem' }}>
                      <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff' }}>
                        Scrutiny Officer Precondition Review & Recommendation
                      </div>
                      <button
                        className="btn-secondary"
                        style={{ fontSize: '0.75rem', borderColor: selectedInstrument.compliance_hold ? '#ef4444' : 'var(--border-color)', color: selectedInstrument.compliance_hold ? '#f87171' : '#fff' }}
                        onClick={handleToggleComplianceHold}
                        disabled={isTogglingHold}
                      >
                        {isTogglingHold ? 'Updating...' : selectedInstrument.compliance_hold ? '🔓 Remove Compliance Hold' : '⛔ Apply Compliance Hold'}
                      </button>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.8rem', marginBottom: '0.8rem' }}>
                      <div>
                        <label className="form-label">Scrutiny Recommendation</label>
                        <select
                          className="filter-select"
                          value={scrutinyRecommendation}
                          onChange={e => setScrutinyRecommendation(e.target.value as any)}
                          style={{ width: '100%' }}
                        >
                          <option value="RECOMMEND_RELEASE">Recommend Release to Approving Authority</option>
                          <option value="FLAG_FOR_AUDIT">Flag Deficiencies / Request Rectification</option>
                        </select>
                      </div>
                      <div>
                        <label className="form-label">Scrutiny Notes & Observations</label>
                        <input
                          type="text"
                          className="form-input"
                          placeholder="e.g. Verified with bank CBS; all certificates in order."
                          value={scrutinyNotes}
                          onChange={e => setScrutinyNotes(e.target.value)}
                        />
                      </div>
                    </div>

                    <button
                      className="btn-secondary"
                      disabled={isScrutinizing || selectedInstrument.status === 'Released' || selectedInstrument.status === 'Replaced'}
                      onClick={handleScrutinizeRelease}
                    >
                      {isScrutinizing ? 'Submitting Recommendation...' : 'Submit Scrutiny Findings'}
                    </button>
                  </div>
                )}

                {/* 3. Approving Authority Panel */}
                {(USERS[currentUserIdx].role === 'APPROVING_AUTHORITY' || USERS[currentUserIdx].role === 'ADMIN') && (
                  <div className="release-action-panel" style={{ border: '1px solid rgba(245,158,11,0.4)', background: 'rgba(245,158,11,0.03)' }}>
                    <div style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--accent-saffron)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span>⚖️ Approving Authority Sanction Console</span>
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                      Only the Approving Authority has the statutory power to sanction release or issue formal rejection.
                    </div>

                    {selectedInstrument.status === 'Released' ? (
                      <div style={{ background: 'rgba(16,185,129,0.1)', padding: '0.85rem', borderRadius: '6px', border: '1px solid rgba(16,185,129,0.3)', color: '#34d399', fontSize: '0.85rem' }}>
                        ✓ Formally Sanctioned & Released on {new Date(selectedInstrument.released_at || '').toLocaleString()} by {selectedInstrument.released_by_username || 'Authority'}. (Order: {selectedInstrument.release_order_reference})
                      </div>
                    ) : (
                      <div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.8rem', marginBottom: '1rem' }}>
                          <div>
                            <label className="form-label">Sanction Order Reference *</label>
                            <input
                              type="text"
                              className="form-input"
                              placeholder="e.g. AICTE/FD/REL/2026/041"
                              value={sanctionOrderRef}
                              onChange={e => setSanctionOrderRef(e.target.value)}
                            />
                          </div>
                          <div>
                            <label className="form-label">Approval Authority Notes</label>
                            <input
                              type="text"
                              className="form-input"
                              placeholder="e.g. Sanctioned following satisfactory scrutiny and 8-yr tenure."
                              value={sanctionNotes}
                              onChange={e => setSanctionNotes(e.target.value)}
                            />
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap', alignItems: 'center' }}>
                          <button
                            className="btn-primary"
                            disabled={
                              isSanctioning ||
                              !selectedInstrument.release_checklist?.all_conditions_met ||
                              !sanctionOrderRef.trim()
                            }
                            onClick={handleApproveRelease}
                            style={{
                              background: selectedInstrument.release_checklist?.all_conditions_met ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : '#475569',
                              borderColor: '#10b981',
                              cursor: selectedInstrument.release_checklist?.all_conditions_met ? 'pointer' : 'not-allowed',
                            }}
                          >
                            {isSanctioning ? 'Sanctioning Order...' : '⚖️ Sanction & Release Deposit'}
                          </button>

                          <div style={{ display: 'flex', gap: '0.4rem', flex: 1, minWidth: '240px' }}>
                            <input
                              type="text"
                              className="form-input"
                              placeholder="Rejection reason if declining..."
                              value={rejectionReasonInput}
                              onChange={e => setRejectionReasonInput(e.target.value)}
                              style={{ flex: 1, fontSize: '0.78rem' }}
                            />
                            <button
                              className="btn-secondary"
                              disabled={isRejecting || !rejectionReasonInput.trim()}
                              onClick={handleRejectRelease}
                              style={{ color: '#fb7185', borderColor: 'rgba(244,63,94,0.4)', fontSize: '0.78rem' }}
                            >
                              {isRejecting ? 'Rejecting...' : 'Reject Release'}
                            </button>
                          </div>
                        </div>

                        {!selectedInstrument.release_checklist?.all_conditions_met && (
                          <div style={{ fontSize: '0.74rem', color: '#fb7185', marginTop: '0.6rem' }}>
                            * Sanction button disabled until all 5 statutory preconditions are satisfied server-side.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* RESOLVE DISCREPANCY MODAL */}
      {resolvingDiscrepancy && (
        <div className="modal-overlay" onClick={() => setResolvingDiscrepancy(null)}>
          <div className="modal-content" style={{ maxWidth: '500px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Resolve Discrepancy</h3>
              <button className="modal-close" onClick={() => setResolvingDiscrepancy(null)}>&times;</button>
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff' }}>{resolvingDiscrepancy.title}</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                Rule: {resolvingDiscrepancy.rule_code} • Severity: {resolvingDiscrepancy.severity}
              </div>
            </div>
            <div className="form-group" style={{ marginBottom: '1.2rem' }}>
              <label className="form-label">Official Resolution Note *</label>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder="Explain justification, verified bank confirmation letter, or rationale for clearing this flag..."
                value={resolutionNote}
                onChange={e => setResolutionNote(e.target.value)}
                required
              ></textarea>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem' }}>
              <button className="btn-secondary" onClick={() => setResolvingDiscrepancy(null)}>Cancel</button>
              <button
                className="btn-primary"
                disabled={!resolutionNote || isResolving}
                onClick={handleResolveDiscrepancy}
              >
                {isResolving ? 'Resolving...' : 'Confirm Resolution'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* FLAG DISCREPANCY MODAL */}
      {isFlagModalOpen && (
        <div className="modal-overlay" onClick={() => setIsFlagModalOpen(false)}>
          <div className="modal-content" style={{ maxWidth: '520px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Flag Discrepancy on Instrument</h3>
              <button className="modal-close" onClick={() => setIsFlagModalOpen(false)}>&times;</button>
            </div>
            <form onSubmit={handleFlagDiscrepancy}>
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Severity Level *</label>
                <select
                  className="form-select"
                  value={flagSeverity}
                  onChange={e => setFlagSeverity(e.target.value as any)}
                >
                  <option value="CRITICAL">CRITICAL (Blocks Verification & Release)</option>
                  <option value="HIGH">HIGH (Significant Risk / Value Discrepancy)</option>
                  <option value="MEDIUM">MEDIUM (Requires Clarification)</option>
                  <option value="LOW">LOW (Informational / Minor Document Defect)</option>
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">Associated Field Name (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. amount, maturity_date, lien_letter"
                  value={flagFieldName}
                  onChange={e => setFlagFieldName(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                <label className="form-label">Discrepancy Description & Reason *</label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="Detail the exact finding, discrepancy from physical verification, or regulatory deviation..."
                  value={flagReason}
                  onChange={e => setFlagReason(e.target.value)}
                  required
                ></textarea>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem' }}>
                <button type="button" className="btn-secondary" onClick={() => setIsFlagModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={!flagReason || isFlagging}>
                  {isFlagging ? 'Flagging...' : 'Save Discrepancy Flag'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* PHASE 6: REPORTS & EXPORTS MODAL */}
      {isReportsModalOpen && (
        <div className="modal-overlay" onClick={() => setIsReportsModalOpen(false)}>
          <div className="modal-content" style={{ maxWidth: '850px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">📊 Regulatory Compliance Reports & Executive Analytics</h3>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '0.2rem 0 0' }}>
                  Download authoritative executive PDF summaries or raw audit CSVs for AICTE governance and committee meetings.
                </p>
              </div>
              <button className="modal-close" onClick={() => setIsReportsModalOpen(false)}>&times;</button>
            </div>

            {/* Weekly Summary Dispatch Action Banner */}
            <div style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: 'var(--radius-md)', padding: '1rem', marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <div style={{ fontWeight: 700, color: '#93c5fd', fontSize: '0.88rem' }}>
                  📬 Scheduled Weekly Regulatory Summary Email
                </div>
                <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginTop: '0.2rem' }}>
                  Celery Beat dispatches this automatically every Monday at 08:00 AM IST to all scrutiny officers and bureau directors.
                </div>
              </div>
              <button
                className="btn-primary"
                style={{ fontSize: '0.78rem', padding: '0.45rem 0.9rem', background: '#2563eb' }}
                disabled={isSendingWeeklySummary}
                onClick={handleSendWeeklySummaryNow}
              >
                {isSendingWeeklySummary ? 'Dispatching Summary...' : '📧 Trigger Weekly Email Now'}
              </button>
            </div>

            {weeklySummaryMsg && (
              <div className="alert-box success" style={{ marginBottom: '1.25rem', fontSize: '0.8rem' }}>
                ✓ {weeklySummaryMsg}
              </div>
            )}

            {/* Reports Grid */}
            <div className="reports-modal-grid">
              {[
                {
                  type: 'pending_verifications',
                  title: 'Pending CBS Verifications',
                  icon: '🏦',
                  desc: 'Instruments submitted by institutions awaiting scrutiny officer and bank CBS confirmation.',
                },
                {
                  type: 'upcoming_maturities',
                  title: 'Upcoming Maturities (90d)',
                  icon: '📅',
                  desc: 'All active security deposits reaching contractual maturity within the next 90 calendar days.',
                },
                {
                  type: 'missing_documents',
                  title: 'Missing & Incomplete Docs',
                  icon: '📄',
                  desc: 'Instruments flagged for missing mandatory FDR certificate scans, lien letters, or unreadable dates.',
                },
                {
                  type: 'overdue_cases',
                  title: 'Overdue & Expired Cases',
                  icon: '🚨',
                  desc: 'Matured deposits that have not been renewed, replaced, or formally released by the institution.',
                },
                {
                  type: 'urgent_intervention',
                  title: 'Cases Needing Intervention',
                  icon: '⚠️',
                  desc: 'High-risk deposits with unresolved critical discrepancy flags or regulatory compliance holds.',
                },
                {
                  type: 'institution_summary',
                  title: 'Institution-wise Summary',
                  icon: '🏢',
                  desc: 'Aggregate institutional portfolio summary, total deposit amounts, active counts, and compliance status.',
                },
              ].map(rep => (
                <div key={rep.type} className="report-export-card">
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                      <span style={{ fontSize: '1.3rem' }}>{rep.icon}</span>
                      <strong style={{ color: '#fff', fontSize: '0.9rem' }}>{rep.title}</strong>
                    </div>
                    <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.4 }}>
                      {rep.desc}
                    </p>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.8rem' }}>
                    <button
                      className="btn-secondary"
                      style={{ flex: 1, fontSize: '0.74rem', padding: '0.4rem 0.5rem' }}
                      disabled={downloadingReportKey === `${rep.type}-csv`}
                      onClick={() => handleDownloadReport(rep.type, 'csv')}
                    >
                      {downloadingReportKey === `${rep.type}-csv` ? 'Generating...' : '📥 CSV Export'}
                    </button>
                    <button
                      className="btn-primary"
                      style={{ flex: 1, fontSize: '0.74rem', padding: '0.4rem 0.5rem' }}
                      disabled={downloadingReportKey === `${rep.type}-pdf`}
                      onClick={() => handleDownloadReport(rep.type, 'pdf')}
                    >
                      {downloadingReportKey === `${rep.type}-pdf` ? 'Generating...' : '📄 Executive PDF'}
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn-secondary" onClick={() => setIsReportsModalOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* PHASE 6: SAVE FILTER PRESET MODAL */}
      {isSaveFilterModalOpen && (
        <div className="modal-overlay" onClick={() => setIsSaveFilterModalOpen(false)}>
          <div className="modal-content" style={{ maxWidth: '480px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">⭐ Save Filter Preset</h3>
              <button className="modal-close" onClick={() => setIsSaveFilterModalOpen(false)}>&times;</button>
            </div>

            <div style={{ marginBottom: '1rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              Save current search criteria as a 1-click filter preset for your account.
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', marginBottom: '1.25rem', fontSize: '0.74rem', border: '1px solid var(--border-color)' }}>
              <div><strong>Status:</strong> {statusFilter}</div>
              {searchQuery && <div><strong>Search:</strong> &ldquo;{searchQuery}&rdquo;</div>}
              {filterBank && <div><strong>Bank:</strong> {filterBank}</div>}
              {filterDiscrepancyType && <div><strong>Discrepancy:</strong> {filterDiscrepancyType}</div>}
              {(filterMinAmount || filterMaxAmount) && (
                <div><strong>Amount:</strong> ₹{filterMinAmount || '0'} - ₹{filterMaxAmount || 'Any'}</div>
              )}
              {(filterMaturityFrom || filterMaturityTo) && (
                <div><strong>Maturity:</strong> {filterMaturityFrom || 'Any'} to {filterMaturityTo || 'Any'}</div>
              )}
            </div>

            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
              <label className="form-label">Preset Name *</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g., Critical SBI Expiring Soon"
                value={saveFilterNameInput}
                onChange={e => setSaveFilterNameInput(e.target.value)}
                autoFocus
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setIsSaveFilterModalOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={!saveFilterNameInput.trim() || isSavingFilter}
                onClick={handleSaveFilter}
              >
                {isSavingFilter ? 'Saving...' : 'Save Preset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
