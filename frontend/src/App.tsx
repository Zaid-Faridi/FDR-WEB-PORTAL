import React, { useEffect, useState, useRef } from 'react';
import { InstrumentItem, DocumentItem, HealthCheckResponse } from './types/provenance';

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

  // Modals
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState<boolean>(false);
  const [selectedInstrument, setSelectedInstrument] = useState<InstrumentItem | null>(null);

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

  // New Version Upload State in Detail Modal
  const [versionDocType, setVersionDocType] = useState<string>('FDR_CERTIFICATE');
  const [versionFile, setVersionFile] = useState<File | null>(null);
  const [uploadingVersion, setUploadingVersion] = useState<boolean>(false);
  const [versionUploadError, setVersionUploadError] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);

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
        setInstruments(Array.isArray(list) ? list : []);
        // Update selectedInstrument if detail modal is open
        if (selectedInstrument) {
          const updated = (Array.isArray(list) ? list : []).find((i: InstrumentItem) => i.id === selectedInstrument.id);
          if (updated) setSelectedInstrument(updated);
        }
      }
    } catch (err) {
      console.error('Fetch instruments error:', err);
    }
  };

  // 3. Health Check
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

    // Client-side file type validation
    const allowedExts = ['.pdf', '.jpg', '.jpeg', '.png'];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedExts.includes(ext)) {
      setSubmitError(`Invalid file format '${ext}'. Only PDF, JPG, and PNG documents are allowed.`);
      setSelectedFile(null);
      return;
    }

    // Client-side size validation (15MB)
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
        // Refresh single instrument
        const singleRes = await fetch(`/api/instruments/${selectedInstrument.id}/`, {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (singleRes.ok) {
          const updated = await singleRes.json();
          setSelectedInstrument(updated);
        }
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

  // Scrutiny Officer: Trigger Bank Verification
  const handleVerify = async (instId: number) => {
    try {
      const res = await fetch(`/api/instruments/${instId}/verify/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ notes: 'Verified via Mock CBS Bank Adapter' }),
      });
      if (res.ok) {
        fetchInstruments(authToken);
      }
    } catch (err) {
      console.error('Verify error:', err);
    }
  };

  // Filter instruments
  const filteredInstruments = instruments.filter(item => {
    const matchesSearch =
      item.reference_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.issuing_bank.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.institution_name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || item.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Calculate statistics
  const totalValue = instruments.reduce((sum, item) => sum + parseFloat(item.amount || '0'), 0);
  const verifiedCount = instruments.filter(i => i.status === 'Verified' || i.status === 'Active').length;
  const discrepancyCount = instruments.filter(i => i.status === 'Discrepancy').length;

  return (
    <div className="portal-container">
      {/* Header */}
      <header className="portal-header">
        <div className="brand-section">
          <div className="gov-emblem">AICTE</div>
          <div>
            <h1 className="portal-title">AICTE Security Deposit & FDR Management Portal</h1>
            <p className="portal-subtitle">Regulation Bureau • Full Lifecycle FDR Verification & Vault</p>
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
      <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
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

      {/* Stats Summary Cards */}
      <section className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Deposit Value</div>
          <div className="stat-value">₹{(totalValue / 100000).toFixed(2)} Lakhs</div>
          <div className="stat-meta">Across {instruments.length} Instruments</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Verified Instruments</div>
          <div className="stat-value" style={{ color: 'var(--accent-emerald)' }}>
            {verifiedCount}
          </div>
          <div className="stat-meta">Bank CBS Confirmed</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Discrepancy Alerts</div>
          <div className="stat-value" style={{ color: discrepancyCount > 0 ? 'var(--accent-rose)' : '#fff' }}>
            {discrepancyCount}
          </div>
          <div className="stat-meta">Requires Attention</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Secure Vault Storage</div>
          <div className="stat-value" style={{ color: 'var(--accent-blue)', fontSize: '1.3rem' }}>
            AES-Fernet
          </div>
          <div className="stat-meta">Encrypted Outside Web Root</div>
        </div>
      </section>

      {/* Section Toolbar */}
      <div className="section-toolbar">
        <h2 className="section-title">
          {USERS[currentUserIdx].role === 'INSTITUTION'
            ? 'Institutional Fixed Deposit Receipts'
            : 'National Institution Deposit Directory'}
        </h2>

        <div className="toolbar-controls">
          <input
            type="text"
            className="search-input"
            placeholder="Search FDR number or bank..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />

          <select
            className="filter-select"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Statuses</option>
            <option value="Submitted">Submitted</option>
            <option value="Under Scrutiny">Under Scrutiny</option>
            <option value="Verified">Verified</option>
            <option value="Active">Active</option>
            <option value="Discrepancy">Discrepancy</option>
            <option value="Release Requested">Release Requested</option>
            <option value="Released">Released</option>
          </select>
        </div>
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
                <th>AICTE Lien</th>
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
                  <td>{item.maturity_date}</td>
                  <td>
                    {item.lien_in_favour_of_aicte ? (
                      <span className="badge badge-confirmed">Lien Active</span>
                    ) : (
                      <span className="badge badge-discrepancy">No Lien</span>
                    )}
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
                        Details
                      </button>
                      {USERS[currentUserIdx].role === 'SCRUTINY_OFFICER' && item.status === 'Submitted' && (
                        <button
                          className="btn-primary"
                          style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                          onClick={() => handleVerify(item.id)}
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

      {/* SUBMIT FDR MODAL */}
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

            <form onSubmit={handleSubmitFDR}>
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">FDR Reference Number *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. FDR-SBI-2026-9901"
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

            {/* Reconciliation Card */}
            <div style={{ marginBottom: '1.5rem', background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <h4 style={{ fontSize: '0.9rem', color: 'var(--accent-saffron)', marginBottom: '0.6rem' }}>
                Claimed vs Bank-Confirmed Reconciliation
              </h4>
              <table className="portal-table" style={{ background: 'transparent' }}>
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Claimed (Institution)</th>
                    <th>Bank Confirmed (CBS)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Principal Amount</td>
                    <td><span className="badge badge-claimed">₹{parseFloat(selectedInstrument.amount).toLocaleString('en-IN')}</span></td>
                    <td>
                      {selectedInstrument.claimed_vs_confirmed?.amount?.confirmed ? (
                        <span className="badge badge-confirmed">₹{parseFloat(selectedInstrument.claimed_vs_confirmed.amount.confirmed.value).toLocaleString('en-IN')}</span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>Pending Scrutiny</span>
                      )}
                    </td>
                  </tr>
                  <tr>
                    <td>Lien Status</td>
                    <td>
                      {selectedInstrument.lien_in_favour_of_aicte ? (
                        <span className="badge badge-claimed">Declared Yes</span>
                      ) : (
                        <span className="badge badge-discrepancy">Declared No</span>
                      )}
                    </td>
                    <td>
                      {selectedInstrument.claimed_vs_confirmed?.lien_in_favour_of_aicte?.confirmed ? (
                        <span className="badge badge-confirmed">Lien Verified</span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>Pending Scrutiny</span>
                      )}
                    </td>
                  </tr>
                  <tr>
                    <td>Maturity Date</td>
                    <td><span className="badge badge-claimed">{selectedInstrument.maturity_date}</span></td>
                    <td>
                      {selectedInstrument.claimed_vs_confirmed?.maturity_date?.confirmed ? (
                        <span className="badge badge-confirmed">{selectedInstrument.claimed_vs_confirmed.maturity_date.confirmed.value}</span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>Pending Scrutiny</span>
                      )}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Document Vault Section */}
            <div style={{ marginBottom: '1.5rem' }}>
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
              <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(15,23,42,0.8)', borderRadius: '8px', border: '1px dashed var(--border-color)' }}>
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

            {/* Remarks History */}
            <div>
              <h4 style={{ fontSize: '0.9rem', color: '#fff', marginBottom: '0.6rem' }}>
                Scrutiny Observations & Remarks Timeline
              </h4>
              {selectedInstrument.remarks?.length === 0 ? (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No remarks recorded yet.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
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
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
