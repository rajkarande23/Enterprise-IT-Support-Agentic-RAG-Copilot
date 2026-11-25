const chat = document.getElementById('chat');
const form = document.getElementById('chatForm');
const question = document.getElementById('question');
const trace = document.getElementById('trace');
const sourceUsed = document.getElementById('sourceUsed');
const ticketCountBadge = document.getElementById('ticketCountBadge');

function escapeHtml(s = '') {
  return String(s).replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
}

function formatText(s = '') {
  return escapeHtml(s).replace(/\n/g, '<br>');
}

function renderTicketCard(ticket) {
  if (!ticket) return '';
  const prioClass = `priority-${(ticket.priority || 'medium').toLowerCase()}`;
  const statusClass = `status-${(ticket.status || 'open').toLowerCase().replace(/\s+/g, '-')}`;
  return `
    <div class="ticket-card">
      <div class="ticket-header">
        <span class="ticket-id">🎫 ${escapeHtml(ticket.ticket_id)}</span>
        <span class="badge ${prioClass}">${escapeHtml(ticket.priority)}</span>
        <span class="badge ${statusClass}">${escapeHtml(ticket.status)}</span>
        <span style="margin-left:auto;font-size:11px;color:#64748b;">${escapeHtml(ticket.category || 'General IT')}</span>
      </div>
      <div class="ticket-body">
        <strong>${escapeHtml(ticket.title)}</strong>
        <p>${escapeHtml(ticket.description)}</p>
      </div>
      <div class="ticket-footer">
        <span>Requester: ${escapeHtml(ticket.requester_email || 'employee')}</span>
      </div>
    </div>
  `;
}

function addMessage(role, text, source = '', citations = [], ticket = null) {
  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;
  const citeHtml = citations && citations.length
    ? `<div class="citations"><strong>Sources</strong><br>${citations.map(c => c.url ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${escapeHtml(c.title)}</a>` : escapeHtml(c.title)).join('<br>')}</div>`
    : '';
  const ticketHtml = ticket ? renderTicketCard(ticket) : '';

  wrap.innerHTML = `
    <div class="avatar">AI</div>
    <div class="bubble">
      ${formatText(text)}
      ${ticketHtml}
      ${source ? `<div class="answer-source">Action: ${escapeHtml(source)}</div>` : ''}
      ${citeHtml}
    </div>
  `;
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
}

function renderTrace(items = []) {
  trace.innerHTML = items.length
    ? items.map(x => `<div class="trace-item">${escapeHtml(x)}</div>`).join('')
    : '<div class="empty">No trace.</div>';
}

async function refreshTicketStats() {
  try {
    const res = await fetch('/api/tickets');
    if (!res.ok) return;
    const data = await res.json();
    if (data.stats && ticketCountBadge) {
      ticketCountBadge.textContent = data.stats.total;
    }
  } catch (err) {
    // silently ignore background badge refresh failures
  }
}

async function askAgent(q) {
  addMessage('user', q);
  question.value = '';
  renderTrace(['Routing question & checking evidence...']);
  sourceUsed.textContent = 'Running';
  const btn = form.querySelector('button');
  btn.disabled = true;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');

    addMessage('assistant', data.answer, data.source_used, data.citations || [], data.ticket);
    renderTrace(data.trace || []);
    sourceUsed.textContent = data.source_used;
    if (data.ticket) {
      refreshTicketStats();
    }
  } catch (e) {
    addMessage('assistant', `Error: ${e.message}`);
    renderTrace(['Request failed']);
    sourceUsed.textContent = 'Error';
  } finally {
    btn.disabled = false;
  }
}

form.addEventListener('submit', e => {
  e.preventDefault();
  const q = question.value.trim();
  if (q) askAgent(q);
});

document.querySelectorAll('.example').forEach(b => {
  b.addEventListener('click', () => askAgent(b.textContent.trim()));
});

// --- Upload Modal ---
const uploadModal = document.getElementById('uploadModal');
document.getElementById('openUpload').onclick = () => uploadModal.classList.remove('hidden');
document.getElementById('closeUpload').onclick = () => uploadModal.classList.add('hidden');
document.getElementById('uploadBtn').onclick = async () => {
  const file = document.getElementById('fileInput').files[0];
  const key = document.getElementById('adminKey').value;
  const status = document.getElementById('uploadStatus');
  if (!file) {
    status.textContent = 'Choose a file first.';
    return;
  }
  status.textContent = 'Indexing document...';
  const fd = new FormData();
  fd.append('file', file);
  try {
    const r = await fetch('/api/ingest', {
      method: 'POST',
      headers: { 'X-Admin-Key': key },
      body: fd,
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Upload failed');
    status.textContent = `Indexed ${d.file}: ${d.chunks} chunks.`;
  } catch (e) {
    status.textContent = `Error: ${e.message}`;
  }
};

// --- Create Ticket Modal ---
const ticketModal = document.getElementById('ticketModal');
const openTicketModalBtn = document.getElementById('openTicketModal');
const closeTicketModalBtn = document.getElementById('closeTicketModal');
const manualTicketForm = document.getElementById('manualTicketForm');
const ticketStatus = document.getElementById('ticketStatus');

openTicketModalBtn.onclick = () => {
  ticketModal.classList.remove('hidden');
  ticketStatus.textContent = '';
};
closeTicketModalBtn.onclick = () => ticketModal.classList.add('hidden');

manualTicketForm.addEventListener('submit', async e => {
  e.preventDefault();
  ticketStatus.textContent = 'Submitting incident ticket...';
  const payload = {
    title: document.getElementById('ticketTitle').value.trim(),
    category: document.getElementById('ticketCategory').value,
    priority: document.getElementById('ticketPriority').value,
    requester_email: document.getElementById('ticketEmail').value.trim(),
    description: document.getElementById('ticketDesc').value.trim(),
  };

  try {
    const res = await fetch('/api/tickets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail || 'Failed to create ticket');
    ticketStatus.textContent = `Success! Created ticket ${d.ticket.ticket_id}`;
    manualTicketForm.reset();
    refreshTicketStats();
    setTimeout(() => {
      ticketModal.classList.add('hidden');
      addMessage('assistant', `Manual Ticket Submitted: **${d.ticket.ticket_id}**`, 'manual_portal', [], d.ticket);
    }, 1200);
  } catch (err) {
    ticketStatus.textContent = `Error: ${err.message}`;
  }
});

// --- View Tickets Dashboard Modal ---
const ticketsListModal = document.getElementById('ticketsListModal');
const openTicketsListModalBtn = document.getElementById('openTicketsListModal');
const closeTicketsListModalBtn = document.getElementById('closeTicketsListModal');
const ticketsContainer = document.getElementById('ticketsContainer');

openTicketsListModalBtn.onclick = () => {
  ticketsListModal.classList.remove('hidden');
  loadTicketsDashboard();
};
closeTicketsListModalBtn.onclick = () => ticketsListModal.classList.add('hidden');

async function loadTicketsDashboard() {
  ticketsContainer.innerHTML = '<div class="empty">Loading tickets...</div>';
  try {
    const res = await fetch('/api/tickets');
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to load tickets');

    // Update stats bar
    document.getElementById('statTotal').textContent = data.stats.total;
    document.getElementById('statOpen').textContent = data.stats.open;
    document.getElementById('statProgress').textContent = data.stats.in_progress;
    document.getElementById('statResolved').textContent = data.stats.resolved;
    if (ticketCountBadge) ticketCountBadge.textContent = data.stats.total;

    if (!data.tickets || data.tickets.length === 0) {
      ticketsContainer.innerHTML = '<div class="empty">No support tickets found. Create one or ask the agent to escalate an issue!</div>';
      return;
    }

    ticketsContainer.innerHTML = data.tickets.map(t => {
      const prioClass = `priority-${(t.priority || 'medium').toLowerCase()}`;
      const statusClass = `status-${(t.status || 'open').toLowerCase().replace(/\s+/g, '-')}`;
      return `
        <div class="ticket-row" data-id="${escapeHtml(t.ticket_id)}">
          <div class="ticket-row-header">
            <div class="ticket-row-meta">
              <span class="ticket-id">${escapeHtml(t.ticket_id)}</span>
              <span class="badge ${prioClass}">${escapeHtml(t.priority)}</span>
              <span class="badge ${statusClass}">${escapeHtml(t.status)}</span>
              <span style="font-size:11px;color:#94a3b8;">${escapeHtml(t.category)}</span>
            </div>
            <div>
              <select class="status-select" onchange="changeTicketStatus('${escapeHtml(t.ticket_id)}', this.value)">
                <option value="Open" ${t.status === 'Open' ? 'selected' : ''}>Open</option>
                <option value="In Progress" ${t.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
                <option value="Resolved" ${t.status === 'Resolved' ? 'selected' : ''}>Resolved</option>
                <option value="Closed" ${t.status === 'Closed' ? 'selected' : ''}>Closed</option>
              </select>
            </div>
          </div>
          <div class="ticket-row-title">${escapeHtml(t.title)}</div>
          <div class="ticket-row-desc">${escapeHtml(t.description)}</div>
          <div class="ticket-row-actions">
            <span>Requester: ${escapeHtml(t.requester_email)}</span>
            <span>Created: ${new Date(t.created_at).toLocaleString()}</span>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    ticketsContainer.innerHTML = `<div class="empty">Error loading tickets: ${escapeHtml(err.message)}</div>`;
  }
}

window.changeTicketStatus = async function (ticketId, newStatus) {
  try {
    const res = await fetch(`/api/tickets/${ticketId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`Error updating ticket: ${err.detail || 'Unknown error'}`);
      return;
    }
    loadTicketsDashboard();
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
};

// Initial badge update
refreshTicketStats();
