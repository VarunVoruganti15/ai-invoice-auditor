// =============================================
// UTILITIES
// =============================================
const fmt = (n) =>
  `₹${Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function showToast(msg) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3100);
}

// =============================================
// AUDIT BUTTON WRAPPERS (desktop + mobile)
// =============================================
const auditBtns = ['audit-btn-desktop', 'audit-btn-mobile'];
const resetBtns = ['reset-btn-desktop', 'reset-btn-mobile'];

function setAuditLoading(loading) {
  auditBtns.forEach(id => {
    const btn = document.getElementById(id);
    if (!btn) return;
    const isMobile = id.includes('mobile');
    const textId = isMobile ? 'audit-btn-text-mobile' : 'audit-btn-text-desktop';
    const spinnerId = isMobile ? 'audit-spinner-mobile' : 'audit-spinner-desktop';
    btn.disabled = loading;
    document.getElementById(textId).textContent = loading ? 'Auditing…' : 'Audit Invoice';
    document.getElementById(spinnerId).style.display = loading ? 'inline-block' : 'none';
  });
}

function setAuditEnabled(enabled) {
  auditBtns.forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = !enabled;
  });
}

// =============================================
// DASHBOARD
// =============================================
async function loadDashboard() {
  try {
    const r = await fetch('/api/dashboard');
    if (!r.ok) return;
    const d = await r.json();
    document.getElementById('val-total').textContent = d.total_invoices;
    document.getElementById('val-billed').textContent = d.total_billed > 0 ? fmt(d.total_billed) : '₹0';
    document.getElementById('val-saved').textContent = d.money_saved > 0 ? fmt(d.money_saved) : '₹0';
    document.getElementById('val-fail').textContent = d.fail_count;
    document.getElementById('val-warn').textContent = d.warning_count;
    renderHistory(d.history);
  } catch (_) { }
}

function renderHistory(history) {
  const panel = document.getElementById('history-panel');
  const tbody = document.getElementById('history-body');
  if (!history || history.length === 0) { panel.style.display = 'none'; return; }
  panel.style.display = 'block';
  tbody.innerHTML = history.map(inv => `
    <tr>
      <td>${inv.invoice_number || '—'}</td>
      <td>${inv.vendor || '—'}</td>
      <td>${fmt(inv.amount)}</td>
      <td><span class="badge badge-${inv.status.toLowerCase()}">${inv.status}</span></td>
    </tr>
  `).join('');
}

// =============================================
// FILE UPLOAD / DROP ZONE
// =============================================
let selectedFile = null;

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const display = document.getElementById('file-name-display');
const fileNameText = document.getElementById('file-name-text');

// Keyboard support
dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
});

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f && f.name.toLowerCase().endsWith('.pdf')) setFile(f);
  else showToast('⚠️ Please select a PDF file');
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

function setFile(f) {
  selectedFile = f;
  fileNameText.textContent = f.name;
  display.style.display = 'flex';
  setAuditEnabled(true);
}

// =============================================
// VENDOR MASTER UPLOAD
// =============================================
const vendorDropZone = document.getElementById('vendor-drop-zone');
const vendorFileInput = document.getElementById('vendor-file-input');
const vendorStatusEl = document.getElementById('vendor-status');
const vendorStatusIcon = document.getElementById('vendor-status-icon');
const vendorStatusText = document.getElementById('vendor-status-text');

function setVendorStatus(type, icon, text) {
  vendorStatusEl.className = `vendor-status vs-${type}`;
  vendorStatusEl.style.display = 'flex';
  vendorStatusIcon.textContent = icon;
  vendorStatusText.textContent = text;
}

async function uploadVendorCSV(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    setVendorStatus('error', '❌', 'Please select a CSV file.');
    return;
  }
  setVendorStatus('loading', '⏳', 'Uploading vendor master…');
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await fetch('/api/upload-vendor-master', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) {
      setVendorStatus('error', '❌', data.detail || 'Upload failed.');
    } else {
      setVendorStatus('success', '✅', `${data.message}`);
    }
  } catch (_) {
    setVendorStatus('error', '❌', 'Network error — try again.');
  }
}

vendorDropZone.addEventListener('click', () => vendorFileInput.click());
vendorDropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); vendorFileInput.click(); }
});
vendorDropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  vendorDropZone.classList.add('drag-over');
});
vendorDropZone.addEventListener('dragleave', () => vendorDropZone.classList.remove('drag-over'));
vendorDropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  vendorDropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) uploadVendorCSV(f);
});
vendorFileInput.addEventListener('change', () => {
  if (vendorFileInput.files[0]) uploadVendorCSV(vendorFileInput.files[0]);
});

// Load existing vendor master status on startup
async function loadVendorMasterStatus() {
  try {
    const res = await fetch('/api/vendor-master');
    if (!res.ok) return;
    const data = await res.json();
    if (data.vendor_count > 0) {
      setVendorStatus('success', '✅', `${data.vendor_count} vendor(s) loaded from default master.`);
    }
  } catch (_) { }
}

// =============================================
// AUDIT
// =============================================
async function runAudit() {
  if (!selectedFile) return;

  setAuditLoading(true);

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('buyer_gstin', document.getElementById('buyer-gstin').value.trim() || '27ABCDE1234F1Z5');

  try {
    const res = await fetch('/api/audit', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok) {
      showToast('❌ ' + (data.detail || 'Audit failed'));
      setAuditLoading(false);
      return;
    }

    renderResults(data);
    await loadDashboard();
    showToast('✅ Audit complete!');

    // Scroll to results on mobile
    if (window.innerWidth < 860) {
      document.getElementById('results-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

  } catch (_) {
    showToast('❌ Network error — try again');
  } finally {
    setAuditLoading(false);
  }
}

auditBtns.forEach(id => {
  const btn = document.getElementById(id);
  if (btn) btn.addEventListener('click', runAudit);
});

// =============================================
// RENDER RESULTS
// =============================================
function renderResults(data) {
  const { fields, result, risk_score, total_impact } = data;

  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('audit-results').style.display = 'block';

  // Fields
  const fieldMap = [
    ['Invoice #', fields.invoice_number || '—'],
    ['Vendor', fields.vendor_name || '—'],
    ['State', result.vendor_state || fields.vendor_state || '—'],
    ['Date', fields.invoice_date || '—'],
    ['GST %', (fields.gst_percent || 0) + '%'],
    ['CGST', fmt(fields.cgst_amount || 0)],
    ['SGST', fmt(fields.sgst_amount || 0)],
    ['IGST', fmt(fields.igst_amount || 0)],
    ['Total', fmt(fields.invoice_total || 0)],
    ['Taxable', fmt(fields.taxable_amount || 0)],
    ['HSN', fields.hsn_code || '—'],
    ['SAC', fields.sac_code || '—'],
  ];

  document.getElementById('fields-grid').innerHTML = fieldMap.map(([label, val]) => `
    <div class="field-chip">
      <div class="field-chip-label">${label}</div>
      <div class="field-chip-value">${val}</div>
    </div>
  `).join('');

  // Vendor master match badge
  const existingBadge = document.getElementById('vendor-match-badge');
  if (existingBadge) existingBadge.remove();
  if (result.vendor_master_matched) {
    const method = result.vendor_match_method === 'GSTIN' ? 'matched by GSTIN ✔' : 'matched by name ✔';
    const badge = document.createElement('div');
    badge.id = 'vendor-match-badge';
    badge.className = 'finding finding-info';
    badge.style.marginBottom = '0.8rem';
    badge.innerHTML = `<span class="finding-icon">🏢</span>Vendor ${method} in Vendor Master${result.vendor_payment_terms ? ` — Payment Terms: <strong>${result.vendor_payment_terms}</strong>` : ''
      }`;
    document.getElementById('fields-grid').after(badge);
  }

  // Status banner
  const bannerEl = document.getElementById('status-banner');
  const statusMap = {
    PASS: { cls: 'status-pass', icon: '✅', text: 'PASS — Invoice Cleared' },
    WARNING: { cls: 'status-warning', icon: '⚠️', text: 'WARNING — Needs Review' },
    FAIL: { cls: 'status-fail', icon: '❌', text: 'FAIL — Risk Detected' },
  };
  const s = statusMap[result.status] || statusMap.FAIL;
  bannerEl.className = `status-banner ${s.cls}`;
  bannerEl.innerHTML = `
    <div class="status-row">
      <span>${s.icon} ${s.text}</span>
      <span class="status-rec">${result.recommendation}</span>
    </div>
    ${total_impact > 0 ? `<div class="leakage-line">💸 Potential Leakage: ${fmt(total_impact)}</div>` : ''}
  `;

  // Risk bar
  document.getElementById('risk-bar-fill').style.width = risk_score + '%';
  document.getElementById('risk-label').textContent = `${risk_score} / 100`;

  // Findings
  const findingsEl = document.getElementById('findings-list');
  if (!result.issues || result.issues.length === 0) {
    findingsEl.innerHTML = '<div class="finding finding-info"><span class="finding-icon">✔️</span> No issues detected</div>';
  } else {
    const typeMap = {
      CRITICAL: { cls: 'finding-critical', icon: '🚨' },
      WARNING: { cls: 'finding-warning', icon: '⚠️' },
      INFO: { cls: 'finding-info', icon: 'ℹ️' },
    };
    findingsEl.innerHTML = result.issues.map(issue => {
      const t = typeMap[issue.type] || typeMap.INFO;
      return `<div class="finding ${t.cls}"><span class="finding-icon">${t.icon}</span>${issue.message}</div>`;
    }).join('');
  }
}

// =============================================
// RESET
// =============================================
async function resetSession() {
  try { await fetch('/api/reset', { method: 'POST' }); } catch (_) { }
  document.getElementById('audit-results').style.display = 'none';
  document.getElementById('empty-state').style.display = 'flex';
  document.getElementById('history-panel').style.display = 'none';
  document.getElementById('history-body').innerHTML = '';
  selectedFile = null;
  display.style.display = 'none';
  fileInput.value = '';
  fileNameText.textContent = '';
  setAuditEnabled(false);
  await loadDashboard();
  showToast('🔄 Session reset');
}

resetBtns.forEach(id => {
  const btn = document.getElementById(id);
  if (btn) btn.addEventListener('click', resetSession);
});

// =============================================
// INIT
// =============================================
loadDashboard();
loadVendorMasterStatus();
