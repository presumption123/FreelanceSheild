const API = '/api/v1';

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (res.status === 401 && !path.includes('/auth/')) {
    showAuth();
    throw new Error('Unauthorized');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail?.error || data.detail || 'Request failed');
  return data;
}

function showAuth() {
  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('app-screen').classList.add('hidden');
}

function showApp() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app-screen').classList.remove('hidden');
}

function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
  document.getElementById(`view-${name}`).classList.remove('hidden');
  document.querySelectorAll('.nav-link[data-view]').forEach(l => l.classList.toggle('active', l.dataset.view === name));
  document.getElementById('page-title').textContent = name.charAt(0).toUpperCase() + name.slice(1);
}

function badge(status) {
  const cls = { OVERDUE: 'badge-overdue', IN_ENFORCEMENT: 'badge-enforcement', PAID: 'badge-paid' }[status] || '';
  return `<span class="badge ${cls}">${status}</span>`;
}

async function loadDashboard() {
  const summary = await api('/dashboard/summary');
  const el = document.getElementById('view-dashboard');
  el.innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><div class="label">Outstanding</div><div class="value">$${summary.totalOutstanding.toLocaleString()}</div></div>
      <div class="stat-card"><div class="label">Overdue</div><div class="value">${summary.overdueCount}</div></div>
      <div class="stat-card"><div class="label">In Enforcement</div><div class="value">${summary.enforcementActiveCount}</div></div>
      <div class="stat-card"><div class="label">Collection Rate</div><div class="value">${(summary.collectionRate * 100).toFixed(0)}%</div></div>
    </div>
    <h3 style="margin-bottom:0.75rem">Aging Buckets</h3>
    <div class="table-wrap"><table>
      <thead><tr><th>Bucket</th><th>Count</th><th>Amount</th></tr></thead>
      <tbody>${summary.agingBuckets.map(b => `<tr><td>${b.label}</td><td>${b.invoiceCount}</td><td>$${b.totalAmount.toLocaleString()}</td></tr>`).join('')}</tbody>
    </table></div>`;
}

async function loadInvoices() {
  const invoices = await api('/invoices');
  const el = document.getElementById('view-invoices');
  el.innerHTML = `
    <div class="form-section">
      <h3>Import CSV</h3>
      <input type="file" id="csv-file" accept=".csv">
      <button class="btn btn-sm" onclick="importCsv()">Upload CSV</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Invoice #</th><th>Client</th><th>Amount</th><th>Due</th><th>Status</th><th>Stage</th><th>Actions</th></tr></thead>
      <tbody>${invoices.map(i => `<tr>
        <td>${i.invoiceNumber}</td>
        <td>${i.client?.name || '—'}</td>
        <td>$${Number(i.amount).toLocaleString()}</td>
        <td>${new Date(i.dueAt).toLocaleDateString()}</td>
        <td>${badge(i.status)}</td>
        <td>${i.escalationStage}</td>
        <td class="actions">
          ${i.status !== 'IN_ENFORCEMENT' && i.status !== 'PAID' ? `<button class="btn btn-sm" onclick="startEnforcement('${i.id}')">Enforce</button>` : ''}
          ${i.status === 'IN_ENFORCEMENT' ? `<button class="btn btn-sm" onclick="advanceEscalation('${i.id}')">Advance</button>` : ''}
          <button class="btn btn-sm btn-success" onclick="markPaid('${i.id}', ${i.amount})">Paid</button>
        </td>
      </tr>`).join('')}</tbody>
    </table></div>`;
}

async function loadClients() {
  const clients = await api('/clients');
  const el = document.getElementById('view-clients');
  el.innerHTML = `
    <div class="form-section">
      <h3>Add Client</h3>
      <div class="form-row">
        <input id="client-name" placeholder="Name">
        <input id="client-email" placeholder="Email" type="email">
      </div>
      <button class="btn btn-sm" onclick="addClient()">Add Client</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Name</th><th>Email</th><th>Outstanding</th><th>Risk</th></tr></thead>
      <tbody>${clients.map(c => `<tr><td>${c.name}</td><td>${c.email}</td><td>$${Number(c.totalOutstanding).toLocaleString()}</td><td>${c.riskScore}</td></tr>`).join('')}</tbody>
    </table></div>`;
}

async function loadDocuments() {
  const docs = await api('/documents');
  const el = document.getElementById('view-documents');
  el.innerHTML = `<div class="table-wrap"><table>
    <thead><tr><th>Filename</th><th>Type</th><th>Created</th><th>Action</th></tr></thead>
    <tbody>${docs.map(d => `<tr><td>${d.filename}</td><td>${d.type}</td><td>${new Date(d.createdAt).toLocaleDateString()}</td>
      <td><a href="${API}/documents/${d.id}/download" class="btn btn-sm">Download</a></td></tr>`).join('')}</tbody>
  </table></div>`;
}

async function loadSettings() {
  const profile = await api('/settings/profile');
  const integrations = await api('/integrations').catch(() => []);
  const el = document.getElementById('view-settings');
  el.innerHTML = `
    <div class="form-section">
      <h3>Profile</h3>
      <p>Name: ${profile.name} · Plan: ${profile.plan} · Jurisdiction: ${profile.jurisdictionCode}</p>
    </div>
    <div class="form-section">
      <h3>Integrations</h3>
      ${['FRESHBOOKS','WAVE','QUICKBOOKS'].map(p => {
        const connected = integrations.find(i => i.provider === p);
        return `<p>${p}: ${connected ? connected.status : 'Not connected'}
          <button class="btn btn-sm" onclick="syncIntegration('${p}')">Sync</button></p>`;
      }).join('')}
    </div>`;
}

async function loadBilling() {
  const usage = await api('/billing/usage');
  const plans = await api('/billing/plans');
  const el = document.getElementById('view-billing');
  el.innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><div class="label">Current Plan</div><div class="value">${usage.plan}</div></div>
      <div class="stat-card"><div class="label">Active Cases</div><div class="value">${usage.activeEnforcementCases}${usage.limit ? ` / ${usage.limit}` : ''}</div></div>
    </div>
    <div class="form-section"><h3>Upgrade</h3>
      ${plans.plans.filter(p => p.id !== 'FREE').map(p => `<button class="btn btn-sm" onclick="checkout('${p.id}')">${p.name} — $${p.price}/mo</button> `).join('')}
    </div>`;
}

async function startEnforcement(id) { await api(`/escalations/${id}/start`, { method: 'POST' }); loadInvoices(); }
async function advanceEscalation(id) { await api(`/escalations/${id}/advance`, { method: 'POST' }); loadInvoices(); }
async function markPaid(id, amount) { await api(`/invoices/${id}/paid`, { method: 'POST', body: JSON.stringify({ amountPaid: amount }) }); loadInvoices(); }
async function addClient() {
  await api('/clients', { method: 'POST', body: JSON.stringify({ name: document.getElementById('client-name').value, email: document.getElementById('client-email').value }) });
  loadClients();
}
async function importCsv() {
  const file = document.getElementById('csv-file').files[0];
  if (!file) return;
  const fd = new FormData(); fd.append('file', file);
  await fetch(`${API}/imports/csv`, { method: 'POST', credentials: 'include', body: fd });
  loadInvoices();
}
async function syncIntegration(p) { await api(`/integrations/${p}/sync`, { method: 'POST' }); alert('Sync complete'); }
async function checkout(plan) {
  try {
    const { checkoutUrl } = await api(`/billing/checkout?plan=${plan}`, { method: 'POST' });
    if (checkoutUrl) window.location.href = checkoutUrl;
  } catch { alert('Stripe not configured — set STRIPE_SECRET_KEY in .env'); }
}

document.querySelectorAll('.nav-link[data-view]').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    const view = link.dataset.view;
    showView(view);
    ({ dashboard: loadDashboard, invoices: loadInvoices, clients: loadClients, documents: loadDocuments, settings: loadSettings, billing: loadBilling })[view]();
  });
});

document.querySelectorAll('#auth-tabs .tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('#auth-tabs .tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('login-form').classList.toggle('hidden', tab.dataset.tab !== 'login');
    document.getElementById('signup-form').classList.toggle('hidden', tab.dataset.tab !== 'signup');
  });
});

document.getElementById('login-form').addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const user = await api('/auth/login', { method: 'POST', body: JSON.stringify({ email: fd.get('email'), password: fd.get('password') }) });
    document.getElementById('user-info').textContent = user.name;
    showApp(); showView('dashboard'); loadDashboard();
  } catch (err) { document.getElementById('auth-error').textContent = err.message; document.getElementById('auth-error').classList.remove('hidden'); }
});

document.getElementById('signup-form').addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api('/auth/signup', { method: 'POST', body: JSON.stringify({ name: fd.get('name'), email: fd.get('email'), password: fd.get('password') }) });
    document.getElementById('login-form').querySelector('[name=email]').value = fd.get('email');
    document.querySelector('[data-tab=login]').click();
    alert('Account created! Log in to continue. Check API response for verification token in dev.');
  } catch (err) { document.getElementById('auth-error').textContent = err.message; document.getElementById('auth-error').classList.remove('hidden'); }
});

document.getElementById('logout-btn').addEventListener('click', async () => {
  await api('/auth/logout', { method: 'POST' });
  showAuth();
});

(async () => {
  try {
    const user = await api('/auth/me');
    document.getElementById('user-info').textContent = user.name;
    showApp(); showView('dashboard'); loadDashboard();
  } catch { showAuth(); }
})();
