async function loadPortal() {
  try {
    const res = await fetch(`/api/v1/portal/${INVOICE_ID}?token=${encodeURIComponent(TOKEN)}`);
    if (!res.ok) throw new Error('Invalid or expired link');
    const data = await res.json();

    document.getElementById('portal-subtitle').textContent =
      `Invoice ${data.invoiceNumber} from ${data.issuerBusinessName || data.issuerName}`;

    const balance = data.amount - data.amountPaid;
    document.getElementById('portal-content').innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">
        <div><strong>Amount Due</strong><br><span style="font-size:1.5rem">$${balance.toLocaleString()}</span></div>
        <div><strong>Days Overdue</strong><br><span style="font-size:1.5rem;color:${data.daysOverdue > 0 ? '#ef4444' : '#22c55e'}">${data.daysOverdue}</span></div>
      </div>
      <p><strong>Issued:</strong> ${new Date(data.issuedAt).toLocaleDateString()}</p>
      <p><strong>Due:</strong> ${new Date(data.dueAt).toLocaleDateString()}</p>
      ${data.description ? `<p><strong>Description:</strong> ${data.description}</p>` : ''}
      <p><strong>Status:</strong> ${data.currentStage.replace(/_/g, ' ')}</p>
      ${data.paymentLinks?.length ? `<div class="payment-links">${data.paymentLinks.map(l =>
        `<a href="${l.url}" target="_blank">${l.label}</a>`).join('')}</div>` : ''}
    `;

    if (data.canDispute) {
      document.getElementById('dispute-section').classList.remove('hidden');
    }
  } catch (err) {
    document.getElementById('portal-content').innerHTML = `<p style="color:#ef4444">${err.message}</p>`;
  }
}

document.getElementById('dispute-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch(`/api/v1/portal/${INVOICE_ID}/dispute?token=${encodeURIComponent(TOKEN)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reason: fd.get('reason'),
      details: fd.get('details'),
      contactEmail: fd.get('contactEmail'),
    }),
  });
  if (res.ok) {
    alert('Dispute submitted. The freelancer will review your response.');
    e.target.reset();
  } else {
    alert('Failed to submit dispute');
  }
});

loadPortal();
