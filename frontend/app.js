const API_BASE = 'http://localhost:8000/api';
let currentPage = 'dashboard';
let chatSessionId = 'session_' + Date.now();
let lastChatQuery = '';
let lastChatResponse = '';
let fleetData = null;
let equipmentContext = null;
let riskChart = null;
let equipmentBarChart = null;
let vibrationChart = null;
let tempChart = null;
let currentEquipment = 'BF-01';
let allAlerts = [];
let currentFilter = 'all';

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  updateLastUpdated();
  checkSystemHealth();
  showPage('dashboard');
  setInterval(checkSystemHealth, 30000);
  setInterval(() => { if(currentPage === 'dashboard') loadFleetStatus(); }, 60000);
  setInterval(updateLastUpdated, 60000);
  initChat();
});

function updateLastUpdated() {
  const el = document.getElementById('last-updated');
  if(el) {
    el.innerHTML = `<span class="last-updated-dot"></span> Last updated: ${new Date().toLocaleTimeString()}`;
  }
}

// --- Page Navigation ---
function showPage(pageName) {
  currentPage = pageName;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  
  const pageEl = document.getElementById(`page-${pageName}`);
  if(pageEl) pageEl.classList.add('active');
  const navEl = document.getElementById(`nav-${pageName}`);
  if(navEl) navEl.classList.add('active');
  
  const titles = {
    dashboard: { title: 'Operations Dashboard', sub: 'Real-time equipment health monitoring' },
    chat: { title: 'Maintenance Wizard Chat', sub: 'AI-powered diagnostic assistant' },
    equipment: { title: 'Equipment Health', sub: 'Detailed sensor metrics and RUL analysis' },
    alerts: { title: 'Alert Center', sub: 'Active warnings and anomalies' },
    reports: { title: 'Reports', sub: 'Generated maintenance reports' },
    knowledge: { title: 'Knowledge Base', sub: 'Manuals, SOPs, and historical data' }
  };
  
  if (titles[pageName]) {
    document.getElementById('page-title').textContent = titles[pageName].title;
    document.getElementById('page-subtitle').textContent = titles[pageName].sub;
  }

  // Initialize specific page
  if (pageName === 'dashboard') initDashboard();
  if (pageName === 'chat') initChat();
  if (pageName === 'equipment') initEquipment();
  if (pageName === 'alerts') initAlerts();
  if (pageName === 'reports') initReports();
  if (pageName === 'knowledge') initKnowledge();
}

// --- System Health Check ---
async function checkSystemHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    
    document.getElementById('api-dot').className = `status-dot ${data.status === 'online' ? 'online' : 'offline'}`;
    document.getElementById('api-status').textContent = data.status === 'online' ? 'Online' : 'Offline';
    
    document.getElementById('ai-dot').className = `status-dot ${data.gemini_configured ? 'online' : 'warning'}`;
    document.getElementById('ai-status').textContent = data.gemini_configured ? 'Active' : 'Missing Key';
  } catch(e) {
    document.getElementById('api-dot').className = 'status-dot offline';
    document.getElementById('api-status').textContent = 'Offline';
  }
}

// --- Dashboard Functions ---
function initDashboard() {
  loadFleetStatus();
}

async function loadFleetStatus() {
  try {
    const res = await fetch(`${API_BASE}/fleet/status`);
    if (!res.ok) throw new Error('Failed to fetch fleet status');
    fleetData = await res.json();
  } catch (e) {
    console.error(e);
    fleetData = getMockFleetData(); // Fallback
  }

  const summary = fleetData.summary;
  
  document.getElementById('kpi-health').textContent = summary.overall_health_pct + '%';
  const healthRing = document.getElementById('health-ring');
  if(healthRing) {
    const circumference = 2 * Math.PI * 24; // r=24
    healthRing.style.strokeDashoffset = circumference - (summary.overall_health_pct / 100) * circumference;
  }
  document.getElementById('kpi-health-trend').innerHTML = `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M12 7a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0V8.414l-4.293 4.293a1 1 0 01-1.414 0L8 10.414l-4.293 4.293a1 1 0 01-1.414-1.414l5-5a1 1 0 011.414 0L11 10.586 14.586 7H12z"/></svg> Overall condition`;

  const totalCriticalHigh = summary.critical + summary.high;
  document.getElementById('kpi-critical').textContent = totalCriticalHigh;
  document.getElementById('kpi-critical-trend').textContent = `${summary.critical} Critical, ${summary.high} High`;
  
  const avgRul = Math.round(fleetData.equipment.reduce((sum, eq) => sum + (eq.rul_hours || 0), 0) / Math.max(fleetData.equipment.length, 1));
  document.getElementById('kpi-rul').textContent = avgRul + 'h';
  document.getElementById('kpi-rul-trend').textContent = 'Across active fleet';

  const anomalies = fleetData.equipment.filter(eq => eq.severity !== 'NORMAL').length;
  document.getElementById('kpi-anomalies').textContent = anomalies;
  document.getElementById('kpi-anomalies-trend').textContent = 'Requiring attention';

  updateRiskChart(summary);
  updateEquipmentBarChart(fleetData.equipment);
  
  const grid = document.getElementById('equipment-grid');
  grid.innerHTML = '';
  fleetData.equipment.forEach(eq => {
    grid.innerHTML += renderEquipmentCard(eq);
  });

  renderPriorityList(fleetData.equipment);

  // Extract alerts
  allAlerts = [];
  fleetData.equipment.forEach(eq => {
    if (eq.alerts && eq.alerts.length > 0) {
      eq.alerts.forEach(alertText => {
        allAlerts.push({
          equipment_id: eq.equipment_id,
          severity: eq.severity,
          text: alertText,
          timestamp: fleetData.timestamp
        });
      });
    }
  });
  document.getElementById('alerts-badge').textContent = allAlerts.length;
  document.getElementById('alerts-badge').style.display = allAlerts.length > 0 ? 'inline-flex' : 'none';
}

function renderEquipmentCard(eq) {
  const isCrit = eq.severity === 'CRITICAL';
  const glowClass = isCrit ? 'pulse-glow' : '';
  const vib = eq.sensor_data.vibration_mm_s || 0;
  const temp = eq.sensor_data.temperature_c || 0;
  
  return `
    <div class="eq-card ${glowClass}" onclick="showPage('equipment'); selectEquipment('${eq.equipment_id}', null)">
      <div class="eq-card-header">
        <div>
          <div class="eq-id">${eq.equipment_id}</div>
          <div class="eq-type">${eq.equipment_type}</div>
        </div>
        <div class="eq-severity sev-${eq.severity}">${eq.severity}</div>
      </div>
      <div class="eq-gauges">
        <div class="gauge-item">
          <label>Vibration (mm/s)</label>
          <div class="gauge-value">${vib.toFixed(1)}</div>
          <div class="gauge-bar"><div class="gauge-fill bg-${getSeverityClass(eq.severity)}" style="width: ${gaugeWidth(vib, 0, 10)}%"></div></div>
        </div>
        <div class="gauge-item">
          <label>Temp (°C)</label>
          <div class="gauge-value">${temp.toFixed(1)}</div>
          <div class="gauge-bar"><div class="gauge-fill bg-${getSeverityClass(eq.severity)}" style="width: ${gaugeWidth(temp, 0, 150)}%"></div></div>
        </div>
      </div>
      <div class="eq-rul">RUL: <strong>${Math.round(eq.rul_hours)}h</strong> (${Math.round(eq.rul_hours/24)}d)</div>
    </div>
  `;
}

function updateRiskChart(summary) {
  const ctx = document.getElementById('riskChart');
  if(!ctx) return;
  if (riskChart) { riskChart.destroy(); riskChart = null; }
  
  riskChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Critical', 'High', 'Medium', 'Normal'],
      datasets: [{
        data: [summary.critical, summary.high, summary.medium, summary.normal],
        backgroundColor: ['#ef4444', '#f97316', '#eab308', '#22c55e'],
        borderWidth: 0,
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '75%',
      plugins: {
        legend: { position: 'right', labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } } },
        tooltip: { backgroundColor: 'rgba(17, 24, 39, 0.9)', titleColor: '#fff', bodyColor: '#fff', padding: 10, cornerRadius: 8 }
      }
    }
  });
}

function updateEquipmentBarChart(equipment) {
  const ctx = document.getElementById('equipmentBarChart');
  if(!ctx) return;
  if (equipmentBarChart) { equipmentBarChart.destroy(); equipmentBarChart = null; }
  
  const sorted = [...equipment].sort((a,b) => a.rul_hours - b.rul_hours).slice(0, 8);
  const labels = sorted.map(e => e.equipment_id);
  const data = sorted.map(e => e.rul_hours);
  const colors = sorted.map(e => getRiskColor(e.severity));
  
  equipmentBarChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Remaining Useful Life (Hours)',
        data: data,
        backgroundColor: colors,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' }, max: 720 },
        y: { grid: { display: false }, ticks: { color: '#94a3b8', font: { family: 'Inter' } } }
      },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: 'rgba(17, 24, 39, 0.9)', cornerRadius: 8 }
      }
    }
  });
}

function renderPriorityList(equipment) {
  const list = document.getElementById('priority-list');
  const sorted = [...equipment]
    .filter(e => e.severity === 'CRITICAL' || e.severity === 'HIGH')
    .sort((a,b) => a.rul_hours - b.rul_hours);
  
  if (sorted.length === 0) {
    list.innerHTML = '<div class="empty-state">No critical priority equipment currently.</div>';
    return;
  }
  
  let html = '';
  sorted.slice(0, 5).forEach((eq, idx) => {
    html += `
      <div class="priority-item">
        <div class="priority-rank">${idx + 1}</div>
        <div>
          <div class="priority-eq-id">${eq.equipment_id} <span class="eq-severity sev-${eq.severity}" style="font-size:10px; margin-left:8px;">${eq.severity}</span></div>
          <div class="priority-issue">RUL: ${Math.round(eq.rul_hours)}h. ${eq.alerts && eq.alerts.length ? eq.alerts[0] : 'Needs inspection.'}</div>
        </div>
        <button class="priority-action btn-sm" onclick="showPage('equipment'); selectEquipment('${eq.equipment_id}', null)">View Details</button>
      </div>
    `;
  });
  list.innerHTML = html;
}

// --- Chat Functions ---
function initChat() {
  document.getElementById('session-display').textContent = chatSessionId.substring(0,12) + '...';
  loadContextEquipment('');
}

async function sendChat() {
  const inputEl = document.getElementById('chat-input');
  const message = inputEl.value.trim();
  if(!message) return;
  
  appendMessage('user', message);
  inputEl.value = '';
  inputEl.style.height = 'auto';
  
  document.getElementById('chat-suggestions').style.display = 'none';
  document.getElementById('feedback-area').style.display = 'none';
  
  showTypingIndicator();
  
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message,
        session_id: chatSessionId,
        equipment_context: equipmentContext
      })
    });
    
    if(!res.ok) throw new Error('API Error');
    const data = await res.json();
    
    removeTypingIndicator();
    lastChatQuery = message;
    lastChatResponse = data.answer;
    appendMessage('ai', parseMarkdown(data.answer), true);
    
    document.getElementById('feedback-area').style.display = 'flex';
  } catch (e) {
    removeTypingIndicator();
    appendMessage('ai', 'Error connecting to AI service. Please ensure the backend is running and GEMINI_API_KEY is set.', false);
  }
}

function sendSuggestion(btn) {
  document.getElementById('chat-input').value = btn.textContent;
  sendChat();
}

function handleChatKey(event) {
  if(event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendChat();
  }
}

function autoResize(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

function appendMessage(role, content, isHTML=false) {
  const container = document.getElementById('chat-messages');
  const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  const avatar = role === 'user' ? '🧑‍🔧' : '🤖';
  const displayContent = isHTML ? content : `<p>${content.replace(/\\n/g, '<br>')}</p>`;
  
  container.innerHTML += `
    <div class="message message-${role}">
      <div class="message-avatar">${avatar}</div>
      <div class="message-bubble">
        ${displayContent}
        <div style="font-size:10px; opacity:0.5; margin-top:8px; text-align:right;">${time}</div>
      </div>
    </div>
  `;
  container.scrollTop = container.scrollHeight;
}

function showTypingIndicator() {
  const container = document.getElementById('chat-messages');
  container.innerHTML += `
    <div class="message message-ai" id="typing-indicator">
      <div class="message-avatar">🤖</div>
      <div class="message-bubble" style="display:flex; gap:4px; padding: 18px;">
        <span class="typing-dot" style="animation: typing 1s infinite; width:6px; height:6px; background:#fff; border-radius:50%;"></span>
        <span class="typing-dot" style="animation: typing 1s infinite 0.2s; width:6px; height:6px; background:#fff; border-radius:50%;"></span>
        <span class="typing-dot" style="animation: typing 1s infinite 0.4s; width:6px; height:6px; background:#fff; border-radius:50%;"></span>
      </div>
    </div>
  `;
  container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById('typing-indicator');
  if(el) el.remove();
}

function parseMarkdown(text) {
  let html = text
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/`(.*?)`/gim, '<code>$1</code>')
    .replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');
  
  // Very basic list parsing
  html = html.replace(/(?:<br\/>)?- (.*)/gim, '<li>$1</li>');
  
  return `<p>${html}</p>`;
}

async function loadContextEquipment(equipmentId) {
  const display = document.getElementById('ctx-data-display');
  if (!equipmentId) {
    equipmentContext = null;
    display.innerHTML = '<i>No specific equipment selected.</i>';
    return;
  }
  
  display.innerHTML = 'Loading...';
  try {
    const res = await fetch(`${API_BASE}/equipment/${equipmentId}/status`);
    if(!res.ok) throw new Error();
    const data = await res.json();
    equipmentContext = data.sensor_data;
    
    display.innerHTML = `
      <strong>${equipmentContext.equipment_id}</strong><br/>
      Temp: ${equipmentContext.temperature_c}°C<br/>
      Vibration: ${equipmentContext.vibration_mm_s} mm/s<br/>
      Pressure: ${equipmentContext.pressure_bar} bar<br/>
      Current: ${equipmentContext.current_amp} A<br/>
      Oil Level: ${equipmentContext.oil_level_pct}%
    `;
  } catch(e) {
    display.innerHTML = 'Error loading context.';
    equipmentContext = null;
  }
}

async function clearChat() {
  document.getElementById('chat-messages').innerHTML = `
    <div class="message message-ai">
      <div class="message-avatar">🤖</div>
      <div class="message-bubble">
        <p>Chat session cleared. How can I help you next?</p>
      </div>
    </div>
  `;
  chatSessionId = 'session_' + Date.now();
  document.getElementById('session-display').textContent = chatSessionId.substring(0,12) + '...';
  document.getElementById('chat-suggestions').style.display = 'flex';
  
  try {
    await fetch(`${API_BASE}/session/${chatSessionId}`, { method: 'DELETE' });
  } catch(e) {}
  showToast('Chat history cleared', 'info');
}

async function submitFeedback(isPositive) {
  try {
    await fetch(`${API_BASE}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: chatSessionId,
        query: lastChatQuery,
        ai_response: lastChatResponse,
        rating: isPositive ? 5 : 1,
        was_helpful: isPositive
      })
    });
    showToast('Thanks for your feedback!', 'success');
    document.getElementById('feedback-area').style.display = 'none';
  } catch (e) {
    showToast('Failed to submit feedback', 'error');
  }
}

// --- Equipment Health Page ---
function initEquipment() {
  selectEquipment('BF-01', document.querySelector('.eq-tab'));
}

async function selectEquipment(equipmentId, tabEl) {
  currentEquipment = equipmentId;
  
  if (tabEl) {
    document.querySelectorAll('.eq-tab').forEach(t => t.classList.remove('active'));
    tabEl.classList.add('active');
  } else {
    document.querySelectorAll('.eq-tab').forEach(t => {
      if(t.textContent === equipmentId) t.classList.add('active');
      else t.classList.remove('active');
    });
  }
  
  const detailEl = document.getElementById('equipment-detail');
  detailEl.innerHTML = '<div class="loading-center"><div class="loader-spinner"></div></div>';
  
  try {
    const res = await fetch(`${API_BASE}/equipment/${equipmentId}/status`);
    if(!res.ok) throw new Error();
    const data = await res.json();
    
    renderEquipmentDetail(data);
  } catch (e) {
    detailEl.innerHTML = '<div class="empty-state">Failed to load equipment data.</div>';
    // Fallback to offline demo
    if (fleetData) {
       const mockEq = fleetData.equipment.find(eq => eq.equipment_id === equipmentId);
       if(mockEq) {
           renderEquipmentDetail({
               equipment_id: mockEq.equipment_id,
               sensor_data: mockEq.sensor_data,
               analysis: {
                   anomaly: { severity: mockEq.severity, alerts: mockEq.alerts },
                   rul: { rul_hours: mockEq.rul_hours, degradation_pct: 35 },
                   diagnosis: { primary_diagnosis: { fault_name: "Demo Mode" }, consolidated_immediate_actions: ["Check connection"] },
                   risk: { risk_level: mockEq.risk_level, factors: ["Offline mode"] }
               }
           });
       }
    }
  }
}

function renderEquipmentDetail(data) {
  const detailEl = document.getElementById('equipment-detail');
  const sensor = data.sensor_data || {};
  const analysis = data.analysis || {};
  const anomaly = analysis.anomaly || {};
  const rul = analysis.rul || { rul_hours: 0, degradation_pct: 0 };
  const diag = analysis.diagnosis || {};
  const risk = analysis.risk || {};
  
  const sevClass = getSeverityClass(anomaly.severity || 'NORMAL');
  
  let html = `
    <div class="detail-header">
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
          <h2>${data.equipment_id} <span style="font-size:14px; color:#94a3b8; font-weight:normal;">${sensor.equipment_type || ''}</span></h2>
          <div class="eq-severity ${sevClass}" style="margin-top:8px; display:inline-block;">${anomaly.severity || 'NORMAL'} STATUS</div>
        </div>
        <div style="display:flex; gap:12px;">
          <button class="btn-sm" onclick="showPage('chat'); document.getElementById('ctx-equipment').value='${data.equipment_id}'; loadContextEquipment('${data.equipment_id}');">Ask AI</button>
          <button class="btn-primary" onclick="showPage('reports'); setTimeout(() => { document.getElementById('report-equipment').value='${data.equipment_id}'; generateReport(); }, 50);">Generate Report</button>
        </div>
      </div>
    </div>
    
    <div style="margin:24px 0;">
      <h3 style="margin-bottom:16px; font-size:16px;">Real-Time Sensors</h3>
      <div class="sensor-grid">
        ${renderSensorCard('Vibration', sensor.vibration_mm_s, 'mm/s', anomaly.severity)}
        ${renderSensorCard('Temperature', sensor.temperature_c, '°C', anomaly.severity)}
        ${renderSensorCard('Pressure', sensor.pressure_bar, 'bar', 'NORMAL')}
        ${renderSensorCard('Current', sensor.current_amp, 'A', 'NORMAL')}
        ${renderSensorCard('RPM', sensor.rpm, 'rpm', 'NORMAL')}
        ${renderSensorCard('Oil Level', sensor.oil_level_pct, '%', 'NORMAL')}
      </div>
    </div>
    
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:24px;">
      <div class="chart-card">
        <h3>AI Diagnosis</h3>
        <p style="margin-top:12px; color:#f59e0b; font-weight:600;">${diag.primary_diagnosis ? diag.primary_diagnosis.fault_name : 'No faults detected'}</p>
        <ul style="margin-top:12px; font-size:13px; padding-left:16px; list-style:disc;">
          ${(diag.consolidated_immediate_actions || []).slice(0,3).map(a => `<li>${a}</li>`).join('') || '<li>Standard monitoring recommended</li>'}
        </ul>
      </div>
      <div class="chart-card">
        <h3>Remaining Useful Life (RUL)</h3>
        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:12px;">
          <div style="font-size:32px; font-weight:800; color:white;">${Math.round(rul.rul_hours)} <span style="font-size:14px; color:#94a3b8; font-weight:normal;">hours</span></div>
          <div style="font-size:13px; color:#94a3b8;">${rul.degradation_pct.toFixed(1)}% degraded</div>
        </div>
        <div style="height:6px; background:rgba(255,255,255,0.1); border-radius:3px; margin-top:16px;">
          <div style="height:100%; width:${Math.max(0, 100 - rul.degradation_pct)}%; background:var(--green); border-radius:3px;"></div>
        </div>
      </div>
    </div>
  `;
  detailEl.innerHTML = html;
}

function renderSensorCard(name, value, unit, statusStr) {
  if (value === undefined || value === null) return '';
  let colorClass = 'sensor-status-ok';
  if (statusStr === 'CRITICAL' || statusStr === 'HIGH') colorClass = 'sensor-status-crit';
  else if (statusStr === 'MEDIUM') colorClass = 'sensor-status-warn';
  
  return `
    <div class="sensor-item">
      <div class="sensor-name">${name}</div>
      <div class="sensor-val ${colorClass}">${Number(value).toFixed(1)} <span class="sensor-unit">${unit}</span></div>
    </div>
  `;
}

// --- Alerts Page ---
function initAlerts() {
  if(allAlerts.length === 0 && !fleetData) {
    loadFleetStatus().then(() => renderAlerts(allAlerts));
  } else {
    renderAlerts(allAlerts);
  }
}

function filterAlerts(level, btn) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentFilter = level;
  
  const filtered = level === 'all' ? allAlerts : allAlerts.filter(a => a.severity === level);
  renderAlerts(filtered);
}

function renderAlerts(alerts) {
  const container = document.getElementById('alerts-list');
  if(alerts.length === 0) {
    container.innerHTML = '<div class="empty-state">No active alerts for this filter.</div>';
    return;
  }
  
  const sorted = [...alerts].sort((a,b) => {
    const weights = {CRITICAL:4, HIGH:3, MEDIUM:2, NORMAL:1};
    return weights[b.severity] - weights[a.severity];
  });
  
  let html = '';
  sorted.forEach(al => {
    const color = getRiskColor(al.severity);
    const icon = al.severity === 'CRITICAL' ? '🛑' : al.severity === 'HIGH' ? '⚠️' : '⚡';
    
    html += `
      <div class="alert-card" style="border-left-color: ${color}">
        <div class="alert-icon" style="background: ${color}20; font-size:20px;">${icon}</div>
        <div class="alert-info">
          <div class="alert-title">${al.equipment_id} — ${al.severity} Alert</div>
          <div class="alert-desc">${al.text}</div>
          <div class="alert-meta">
            <span>Detected: ${formatTime(al.timestamp)}</span>
          </div>
          <div class="alert-actions">
            <button class="btn-sm" onclick="showPage('chat'); document.getElementById('ctx-equipment').value='${al.equipment_id}'; loadContextEquipment('${al.equipment_id}'); sendSuggestion({textContent:'Analyze ${al.severity} alert on ${al.equipment_id}'})">Diagnose with AI</button>
          </div>
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

// --- Reports Page ---
function initReports() {
  fetchReportsList();
}

async function fetchReportsList() {
  try {
    const res = await fetch(`${API_BASE}/reports/list`);
    const data = await res.json();
    renderReportList(data.reports || []);
  } catch(e) {
    document.getElementById('reports-list').innerHTML = '<div class="empty-state-sm">Could not load history.</div>';
  }
}

function renderReportList(reports) {
  const list = document.getElementById('reports-list');
  if(reports.length === 0) {
    list.innerHTML = '<div class="empty-state-sm">No recent reports</div>';
    return;
  }
  
  list.innerHTML = reports.map(r => `
    <div style="padding:12px; border:1px solid var(--border); border-radius:8px; margin-bottom:8px; cursor:pointer;" class="kb-result-item" onclick="showToast('Report viewing not implemented in demo', 'info')">
      <div style="font-weight:600; font-size:13px; color:white;">${r.equipment_id} Report</div>
      <div style="font-size:11px; color:var(--text-muted); margin-top:4px;">${formatTime(r.timestamp)}</div>
    </div>
  `).join('');
}

async function generateReport() {
  const eqId = document.getElementById('report-equipment').value;
  const viewer = document.getElementById('report-viewer');
  
  viewer.innerHTML = '<div class="report-placeholder"><div class="loader-spinner"></div><p>Generating comprehensive AI report for ' + eqId + '...</p></div>';
  
  try {
    const res = await fetch(`${API_BASE}/reports/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ equipment_id: eqId })
    });
    
    if(!res.ok) throw new Error();
    const data = await res.json();
    
    viewer.innerHTML = `<div class="report-content">${parseMarkdown(data.report_markdown)}</div>`;
    fetchReportsList();
    showToast('Report generated successfully', 'success');
  } catch(e) {
    viewer.innerHTML = '<div class="report-placeholder"><p>Failed to generate report. Ensure backend API is reachable.</p></div>';
    showToast('Error generating report', 'error');
  }
}

// --- Knowledge Base ---
function initKnowledge() {
  loadKBStats();
}

async function loadKBStats() {
  const statsEl = document.getElementById('kb-stats');
  try {
    const res = await fetch(`${API_BASE}/kb/stats`);
    const data = await res.json();
    statsEl.innerHTML = `
      <div style="display:flex; justify-content:space-around; text-align:center; padding: 20px 0;">
        <div>
          <div style="font-size:28px; font-weight:700; color:white;">${data.total_documents || 0}</div>
          <div style="font-size:12px; color:var(--text-muted);">Indexed Chunks</div>
        </div>
        <div>
          <div style="font-size:28px; font-weight:700; color:white;">${data.embedding_model === 'all-MiniLM-L6-v2' ? 'MiniLM' : 'Active'}</div>
          <div style="font-size:12px; color:var(--text-muted);">Embedding Model</div>
        </div>
      </div>
    `;
  } catch(e) {
    statsEl.innerHTML = '<div class="empty-state-sm">Offline</div>';
  }
}

function searchKB() {
  const input = document.getElementById('kb-search-input').value.trim();
  if(!input) return;
  
  showPage('chat');
  document.getElementById('chat-input').value = `Find information about: ${input}`;
  sendChat();
}

async function uploadDocument(input) {
  if(!input.files || input.files.length === 0) return;
  const file = input.files[0];
  
  const status = document.getElementById('upload-status');
  status.innerHTML = `<div style="margin-top:12px; font-size:12px; color:var(--amber);">Uploading and indexing ${file.name}...</div>`;
  
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const res = await fetch(`${API_BASE}/ingest`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if(!res.ok) throw new Error(data.detail || 'Upload failed');
    
    status.innerHTML = `<div style="margin-top:12px; font-size:12px; color:var(--green);">✅ ${data.message}</div>`;
    showToast('Document indexed successfully', 'success');
    loadKBStats();
  } catch(e) {
    status.innerHTML = `<div style="margin-top:12px; font-size:12px; color:var(--red);">❌ ${e.message}</div>`;
    showToast(e.message, 'error');
  }
  input.value = ''; // reset
}

function handleDrop(event) {
  event.preventDefault();
  const dt = event.dataTransfer;
  const files = dt.files;
  if(files.length > 0) {
    const input = document.getElementById('file-input');
    input.files = files;
    uploadDocument(input);
  }
}

// --- Utility Functions ---
function refreshAll() {
  const btn = document.querySelector('.btn-refresh');
  btn.classList.add('spinning');
  
  if(currentPage === 'dashboard') loadFleetStatus();
  else if(currentPage === 'equipment') selectEquipment(currentEquipment, null);
  else if(currentPage === 'knowledge') loadKBStats();
  
  setTimeout(() => btn.classList.remove('spinning'), 800);
}

function handlePlantChange(plant) {
  showToast(`Switched to ${plant.charAt(0).toUpperCase() + plant.slice(1)} Plant`, 'info');
  refreshAll();
}

function showToast(message, type='info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  toast.innerHTML = `<span>${icons[type]}</span> <span>${message}</span>`;
  
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function getRiskColor(level) {
  const map = { 'CRITICAL': '#ef4444', 'HIGH': '#f97316', 'MEDIUM': '#eab308', 'NORMAL': '#22c55e', 'LOW': '#22c55e' };
  return map[level] || '#94a3b8';
}

function getSeverityClass(level) {
  return `sev-${level}`;
}

function gaugeWidth(val, min, max) {
  let pct = ((val - min) / (max - min)) * 100;
  return Math.max(0, Math.min(100, pct));
}

function formatTime(isoString) {
  if(!isoString) return 'Unknown';
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  } catch(e) { return isoString; }
}

function getMockFleetData() {
  return {
    timestamp: new Date().toISOString(),
    total_equipment: 10,
    summary: { critical: 1, high: 2, medium: 3, normal: 4, overall_health_pct: 70 },
    equipment: [
      { equipment_id: 'BF-01', equipment_type: 'BF', severity: 'HIGH', risk_level: 'HIGH', rul_hours: 142, alerts: ['⚡ WARNING: temperature_c = 102.3 (limit: 100)'], sensor_data: { temperature_c: 102.3, vibration_mm_s: 2.8, oil_level_pct: 45 } },
      { equipment_id: 'BF-02', equipment_type: 'BF', severity: 'NORMAL', risk_level: 'LOW', rul_hours: 580, alerts: [], sensor_data: { temperature_c: 68, vibration_mm_s: 1.5, oil_level_pct: 78 } },
      { equipment_id: 'RM-01', equipment_type: 'RM', severity: 'CRITICAL', risk_level: 'CRITICAL', rul_hours: 18, alerts: ['⚠️ CRITICAL: vibration_mm_s = 8.1 (limit: 7.0)', '⚡ WARNING: temperature_c = 98 (limit: 95)'], sensor_data: { temperature_c: 98, vibration_mm_s: 8.1, oil_level_pct: 22 } },
      { equipment_id: 'RM-02', equipment_type: 'RM', severity: 'MEDIUM', risk_level: 'MEDIUM', rul_hours: 290, alerts: [], sensor_data: { temperature_c: 87, vibration_mm_s: 3.2, oil_level_pct: 62 } },
      { equipment_id: 'PUMP-01', equipment_type: 'PUMP', severity: 'NORMAL', risk_level: 'LOW', rul_hours: 620, alerts: [], sensor_data: { temperature_c: 55, vibration_mm_s: 1.2, oil_level_pct: 85 } },
      { equipment_id: 'PUMP-02', equipment_type: 'PUMP', severity: 'HIGH', risk_level: 'HIGH', rul_hours: 65, alerts: ['⚡ WARNING: oil_level_pct = 18 (limit: 20)'], sensor_data: { temperature_c: 72, vibration_mm_s: 2.1, oil_level_pct: 18 } },
      { equipment_id: 'CONV-01', equipment_type: 'CONV', severity: 'NORMAL', risk_level: 'LOW', rul_hours: 510, alerts: [], sensor_data: { temperature_c: 48, vibration_mm_s: 1.0, oil_level_pct: 74 } },
      { equipment_id: 'CONV-02', equipment_type: 'CONV', severity: 'MEDIUM', risk_level: 'MEDIUM', rul_hours: 190, alerts: [], sensor_data: { temperature_c: 62, vibration_mm_s: 3.0, oil_level_pct: 50 } },
      { equipment_id: 'COMP-01', equipment_type: 'COMP', severity: 'NORMAL', risk_level: 'LOW', rul_hours: 445, alerts: [], sensor_data: { temperature_c: 60, vibration_mm_s: 1.8, oil_level_pct: 70 } },
      { equipment_id: 'COMP-02', equipment_type: 'COMP', severity: 'NORMAL', risk_level: 'LOW', rul_hours: 500, alerts: [], sensor_data: { temperature_c: 58, vibration_mm_s: 1.6, oil_level_pct: 72 } }
    ]
  };
}
