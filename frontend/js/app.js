import { renderIncidentFeed, updateLiveCountdowns, formatMoney, formatCountdown, getRemainingSeconds } from './incident-feed.js';
import { initMap, renderIncidentOnMap, recenterMap } from './map-engine.js';
import { renderMuleGraph } from './mule-graph.js';
import { createScenarioIncident, runScenarioSteps } from './simulation-engine.js';
import {
  getRuntimeConfig,
  fetchLiveIncidents,
  fetchHealth,
  fetchDashboardSummary,
  fetchCaseDetail,
  fetchCaseNetwork,
  requestPrediction,
  mapCaseToIncident,
  connectTelemetry
} from './api-client.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const IST_FORMATTER = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const UTC_FORMATTER = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const runtimeConfig = getRuntimeConfig();

const state = {
  incidents: [],
  selectedId: null,
  filter: 'all',
  search: '',
  scenarioRunning: false,
  lastShownThresholds: new Map(),
  eventCount: 0,
  backendSummary: null,
  backendConnected: false
};

const fallbackRecords = [
  {
    id: 'NCRP-2026-9042', city: 'Indore', state: 'Madhya Pradesh', area: 'Vijay Nagar', fraudType: 'Investment APK Scam', amountINR: 320000, remainingSeconds: 702, confidence: 89, muleRingLinked: true, complaintReceived: '12:14:08 IST', status: 'FORECAST GENERATED',
    source: { lat: 22.7534, lon: 75.8918, label: 'Last digital transaction' },
    predictedExit: { name: 'Axis ATM #4401 (fictional demo label)', type: 'BANK ATM', bank: 'Axis Bank', address: 'Scheme 54 service road, Vijay Nagar, Indore', landmark: 'Near Scheme 54 commercial block', lat: 22.7467, lon: 75.8947, radiusMeters: 280, etaMinutes: 4.2, suspectToken: 'CARD •••• 4401', facilityId: 'DEMO-ATM-4401' },
    patrol: { unitId: 'PCR-06', lat: 22.7592, lon: 75.8826, etaMinutes: 4.2, state: 'STANDBY' },
    cashpoints: [{ id: 'CP-01', type: 'ATM', name: 'HDFC ATM (demo marker)', lat: 22.7489, lon: 75.8899 }, { id: 'CP-02', type: 'CSP', name: 'CSP / AEPS kiosk (demo marker)', lat: 22.7449, lon: 75.8992 }, { id: 'CP-03', type: 'ATM', name: 'SBI ATM (demo marker)', lat: 22.7517, lon: 75.8998 }],
    transactionPath: [{ label: 'VICTIM', bank: 'SBI', amountINR: 320000 }, { label: 'TIER-1 MULE', bank: 'HDFC Bank', amountINR: 314500 }, { label: 'TIER-2 MULE', bank: 'Airtel Payments', amountINR: 287000 }, { label: 'FLAGGED EXIT', bank: 'Axis ATM #4401', amountINR: 180000 }], analystNote: 'Synthetic demo fallback record.'
  },
  {
    id: 'NCRP-2026-8917', city: 'Delhi', state: 'Delhi', area: 'Lajpat Nagar', fraudType: 'UPI Collect / Phishing', amountINR: 475000, remainingSeconds: 842, confidence: 82, muleRingLinked: true, complaintReceived: '12:11:32 IST', status: 'GRAPH CORRELATED',
    source: { lat: 28.5701, lon: 77.2412, label: 'Last digital transaction' }, predictedExit: { name: 'Demo Cash Point DL-12', type: 'CSP / AEPS', bank: 'Payments channel (simulated)', address: 'Central Market approach, Lajpat Nagar, Delhi', landmark: 'Near Lajpat Nagar Central Market', lat: 28.5679, lon: 77.2431, radiusMeters: 260, etaMinutes: 5.1, suspectToken: 'AEPS HASH ••7A9C', facilityId: 'DEMO-CSP-DL12' },
    patrol: { unitId: 'PCR-DL-12', lat: 28.5743, lon: 77.2344, etaMinutes: 5.1, state: 'STANDBY' }, cashpoints: [{ id: 'DL-CP-01', type: 'ATM', name: 'Bank ATM (demo marker)', lat: 28.5691, lon: 77.2377 }, { id: 'DL-CP-02', type: 'CSP', name: 'AEPS point (demo marker)', lat: 28.5658, lon: 77.2464 }], transactionPath: [{ label: 'VICTIM', bank: 'ICICI Bank', amountINR: 475000 }, { label: 'TIER-1 MULE', bank: 'Kotak Bank', amountINR: 460000 }, { label: 'TIER-2 MULE', bank: 'Payments Bank', amountINR: 402000 }, { label: 'FLAGGED EXIT', bank: 'Demo Cash Point DL-12', amountINR: 175000 }], analystNote: 'Synthetic demo fallback record.'
  },
  {
    id: 'NCRP-2026-9008', city: 'Indore', state: 'Madhya Pradesh', area: 'Palasia', fraudType: 'Remote Access / APK Dropper', amountINR: 185000, remainingSeconds: 1312, confidence: 76, muleRingLinked: false, complaintReceived: '12:08:21 IST', status: 'HOTSPOT UNDER REVIEW',
    source: { lat: 22.7277, lon: 75.8842, label: 'Last digital transaction' }, predictedExit: { name: 'Demo ATM PL-07', type: 'BANK ATM', bank: 'Bank ATM (simulated)', address: 'AB Road frontage, Palasia, Indore', landmark: 'Near Palasia square service lane', lat: 22.7248, lon: 75.8817, radiusMeters: 300, etaMinutes: 3.8, suspectToken: 'CARD •••• 0927', facilityId: 'DEMO-ATM-PL07' },
    patrol: { unitId: 'PCR-03', lat: 22.7335, lon: 75.8918, etaMinutes: 3.8, state: 'STANDBY' }, cashpoints: [{ id: 'PL-CP-01', type: 'ATM', name: 'ATM south (demo marker)', lat: 22.7218, lon: 75.8862 }, { id: 'PL-CP-02', type: 'CSP', name: 'CSP booth (demo marker)', lat: 22.7271, lon: 75.8771 }], transactionPath: [{ label: 'VICTIM', bank: 'Bank of Baroda', amountINR: 185000 }, { label: 'TIER-1 MULE', bank: 'Federal Bank', amountINR: 181000 }, { label: 'TIER-2 MULE', bank: 'UPI wallet', amountINR: 150000 }, { label: 'FLAGGED EXIT', bank: 'Demo ATM PL-07', amountINR: 80000 }], analystNote: 'Synthetic demo fallback record.'
  },
  {
    id: 'NCRP-2026-8991', city: 'Bhopal', state: 'Madhya Pradesh', area: 'MP Nagar Zone 2', fraudType: 'Task / Job Investment Scam', amountINR: 825000, remainingSeconds: 458, confidence: 93, muleRingLinked: true, complaintReceived: '12:16:47 IST', status: 'EXIT VELOCITY HIGH',
    source: { lat: 23.2352, lon: 77.4319, label: 'Last digital transaction' }, predictedExit: { name: 'Demo ATM BPL-24', type: 'BANK ATM', bank: 'Axis Bank (simulated)', address: 'Zone 2 commercial lane, MP Nagar, Bhopal', landmark: 'Near MP Nagar Zone 2 market frontage', lat: 23.2338, lon: 77.4352, radiusMeters: 240, etaMinutes: 6.5, suspectToken: 'CARD •••• 4812', facilityId: 'DEMO-ATM-BPL24' },
    patrol: { unitId: 'PCR-BPL-04', lat: 23.2416, lon: 77.4249, etaMinutes: 6.5, state: 'STANDBY' }, cashpoints: [{ id: 'BPL-CP-01', type: 'ATM', name: 'ATM cluster A (demo marker)', lat: 23.2311, lon: 77.4287 }, { id: 'BPL-CP-02', type: 'CSP', name: 'AEPS point B (demo marker)', lat: 23.2361, lon: 77.4382 }], transactionPath: [{ label: 'VICTIM', bank: 'SBI', amountINR: 825000 }, { label: 'TIER-1 MULE', bank: 'HDFC Bank', amountINR: 801000 }, { label: 'TIER-2 MULE', bank: 'Payments Bank', amountINR: 744000 }, { label: 'FLAGGED EXIT', bank: 'Demo ATM BPL-24', amountINR: 340000 }], analystNote: 'Synthetic demo fallback record.'
  },
  {
    id: 'NCRP-2026-9028', city: 'Delhi', state: 'Delhi', area: 'Dwarka Sector 12', fraudType: 'SIM Swap / UPI Takeover', amountINR: 275000, remainingSeconds: 1690, confidence: 71, muleRingLinked: true, complaintReceived: '12:04:52 IST', status: 'MULE PATH PARTIAL',
    source: { lat: 28.5947, lon: 77.0452, label: 'Last digital transaction' }, predictedExit: { name: 'Demo CSP DW-09', type: 'CSP / AEPS', bank: 'AEPS channel (simulated)', address: 'Sector 12 market approach, Dwarka, Delhi', landmark: 'Near Sector 12 market access road', lat: 28.5918, lon: 77.0476, radiusMeters: 300, etaMinutes: 3.5, suspectToken: 'AEPS HASH ••91D2', facilityId: 'DEMO-CSP-DW09' },
    patrol: { unitId: 'PCR-DW-09', lat: 28.6002, lon: 77.0402, etaMinutes: 3.5, state: 'STANDBY' }, cashpoints: [{ id: 'DW-CP-01', type: 'ATM', name: 'ATM west (demo marker)', lat: 28.5889, lon: 77.0444 }, { id: 'DW-CP-02', type: 'CSP', name: 'AEPS booth (demo marker)', lat: 28.5908, lon: 77.0523 }], transactionPath: [{ label: 'VICTIM', bank: 'Punjab National Bank', amountINR: 275000 }, { label: 'TIER-1 MULE', bank: 'IndusInd Bank', amountINR: 266000 }, { label: 'TIER-2 MULE', bank: 'UPI wallet', amountINR: 224000 }, { label: 'FLAGGED EXIT', bank: 'Demo CSP DW-09', amountINR: 90000 }], analystNote: 'Synthetic demo fallback record.'
  }
];

function normalizedIncident(record) {
  const remaining = Math.max(0, Number(record.remainingSeconds) || 0);
  return {
    ...record,
    deadlineMs: Number.isFinite(record.deadlineMs) ? record.deadlineMs : Date.now() + remaining * 1000,
    remainingSeconds: remaining,
    initialWindowSeconds: Number(record.initialWindowSeconds) || remaining || 1800,
    patrol: { ...record.patrol, state: record.patrol?.state || 'STANDBY' },
    switchHoldState: record.switchHoldState || 'NOT REQUESTED'
  };
}

async function loadIncidents() {
  const backendRecords = [];
  try {
    if (runtimeConfig.apiBaseUrl) {
      // 1. Verify health with backend
      try {
        const health = await fetchHealth(runtimeConfig);
        if (health && health.status) {
          state.backendConnected = true;
          const streamLabel = $('#stream-label');
          if (streamLabel) streamLabel.textContent = 'STREAM ACTIVE · FASTAPI / s390x';
          const tag = $('#backend-status-tag');
          if (tag) {
            tag.textContent = 'FASTAPI VERIFIED';
            tag.style.background = '#0f5132';
            tag.style.color = '#d1e7dd';
          }
          addLog(`Backend connected: health=${health.status}, DB=${health.database}, ML=${health.ml_service?.status || 'ready'}`, 'data');
        }
      } catch (healthErr) {
        console.warn('Backend health check warning:', healthErr);
      }

      // 2. Fetch dashboard summary if connected
      if (state.backendConnected) {
        try {
          const summary = await fetchDashboardSummary(runtimeConfig);
          if (summary) {
            state.backendSummary = summary;
          }
        } catch (sumErr) {
          console.warn('Dashboard summary fetch warning:', sumErr);
        }
      }

      // 3. Fetch verified cases from backend
      const rawCases = await fetchLiveIncidents(runtimeConfig);
      if (Array.isArray(rawCases) && rawCases.length > 0) {
        for (const rawCase of rawCases) {
          const caseId = rawCase.id || rawCase.case_id;
          const detail = await fetchCaseDetail(caseId, runtimeConfig).catch(() => null);
          const network = await fetchCaseNetwork(caseId, runtimeConfig).catch(() => null);
          const mapped = mapCaseToIncident(rawCase, detail, network);
          backendRecords.push(normalizedIncident(mapped));
        }
        addLog(`Loaded ${backendRecords.length} verified case record(s) from MATRIX backend database.`, 'data');
      }
    }
  } catch (error) {
    console.warn('Live API load warning:', error);
    addLog(`Live API load warning (${error.message}); supplementary demo feed active.`, 'warning');
  }

  // Also load mock incidents for demonstration catalog variety
  let mockList = [];
  try {
    const response = await fetch(new URL('../data/mock-incidents.json', import.meta.url), { cache: 'no-store' });
    if (response.ok) {
      const payload = await response.json();
      if (Array.isArray(payload.records)) {
        mockList = payload.records.map(normalizedIncident);
      }
    }
  } catch {
    mockList = fallbackRecords.map(normalizedIncident);
  }

  if (backendRecords.length > 0) {
    const backendIds = new Set(backendRecords.map((r) => r.id));
    const combined = [...backendRecords, ...mockList.filter((m) => !backendIds.has(m.id))];
    showToast(`Loaded ${backendRecords.length} verified case(s) from LinuxONE backend.`, 'success');
    return combined;
  }

  if (mockList.length > 0) return mockList;
  return fallbackRecords.map(normalizedIncident);
}

function currentIncident() {
  return state.incidents.find((incident) => incident.id === state.selectedId) || null;
}

function addLog(message, type = 'info') {
  const list = $('#event-log');
  if (!list) return;
  state.eventCount += 1;
  const item = document.createElement('li');
  const time = document.createElement('time');
  time.textContent = IST_FORMATTER.format(new Date());
  const text = document.createElement('span');
  text.textContent = message;
  if (type === 'warning') text.className = 'amber-text';
  else if (type === 'dispatch') text.className = 'green-text';
  else if (type === 'demo') text.className = 'event-type';
  item.append(time, text);
  list.prepend(item);
  while (list.children.length > 35) list.lastElementChild.remove();
}

let toastTimer = null;
function showToast(message, kind = 'info') {
  const region = $('#toast-region');
  if (!region) return;
  const toast = document.createElement('div');
  toast.className = `toast${kind === 'warning' ? ' toast-warning' : kind === 'success' ? ' toast-success' : ''}`;
  toast.textContent = message;
  region.append(toast);
  window.setTimeout(() => toast.remove(), 4200);
  if (toastTimer) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { region.replaceChildren(); }, 4600);
}

function renderFeed() {
  const count = renderIncidentFeed({
    container: $('#incident-list'), incidents: state.incidents, selectedId: state.selectedId,
    filter: state.filter, search: state.search,
    onSelect: (id) => selectIncident(id, { fit: true, reason: 'manual selection' })
  });
  $('#incident-count').textContent = String(count).padStart(2, '0');
  $('#filter-all-count').textContent = String(state.incidents.length).padStart(2, '0');
}

function renderKpis() {
  const now = Date.now();
  const open = state.incidents.filter((item) => getRemainingSeconds(item, now) > 0);
  const golden = open.filter((item) => getRemainingSeconds(item, now) <= 1800);
  const capital = state.backendSummary
    ? (state.backendSummary.total_defrauded_amount || 0)
    : golden.reduce((sum, item) => sum + (Number(item.amountINR) || 0), 0);
  const active = currentIncident();
  const avgEta = open.length ? open.reduce((sum, item) => sum + (Number(item.patrol?.etaMinutes) || 0), 0) / open.length : 0;
  
  const activeCount = state.backendSummary
    ? (state.backendSummary.total_cases_open ?? golden.length)
    : golden.length;

  $('#kpi-active').textContent = String(activeCount).padStart(2, '0');
  $('#kpi-active-foot').textContent = state.backendSummary
    ? `${state.backendSummary.total_cases} case(s) in verified database`
    : (golden.length ? `${open.length} open · ≤30-minute model window` : 'No active golden-window records');
  $('#kpi-capital').textContent = formatLakh(capital);
  $('#kpi-capital-foot').textContent = state.backendSummary
    ? `${state.backendSummary.total_transactions_flagged} flagged transactions · verified DB`
    : `${golden.filter((item) => item.muleRingLinked).length} linked ring(s) · synthetic exposure`;
  $('#kpi-radius').textContent = `≤ ${active?.predictedExit?.radiusMeters ?? '—'}`;
  $('#kpi-units').textContent = '06';
  $('#kpi-eta').textContent = `Average ETA ${avgEta.toFixed(1)} min · demo units`;
}

function formatLakh(amount) {
  if (amount >= 100000) return `₹${(amount / 100000).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}L`;
  return formatMoney(amount);
}

function updateMapLabels(incident) {
  const exit = incident.predictedExit;
  const remaining = getRemainingSeconds(incident);
  $('#map-incident-label').textContent = `TARGET: #${incident.id}`;
  $('#map-area-label').textContent = `${incident.city.toUpperCase()} / ${incident.area.toUpperCase()}`;
  $('#map-coordinates').textContent = `${Number(exit.lat).toFixed(4)}° N · ${Number(exit.lon).toFixed(4)}° E`;
  $('#map-radius-overlay').textContent = `R ${exit.radiusMeters} M`;
  $('#map-confidence-overlay').textContent = `${Math.round(incident.confidence)}% CERTAINTY`;
  $('#map-countdown-overlay').textContent = remaining > 0 ? `T− ${formatCountdown(remaining)}` : 'T− 00:00';
  $('#map-window-state').textContent = remaining <= 0 ? 'WINDOW EXPIRED' : remaining <= 900 ? 'CRITICAL WINDOW' : 'INTERCEPTABLE';
  $('#map-window-state').classList.toggle('amber-text', remaining > 0);
  $('#map-unit-state').textContent = incident.patrol.state || 'STANDBY';
  $('#map-updated').textContent = `UPDATED ${IST_FORMATTER.format(new Date())}`;
}

function renderIntel(incident) {
  const exit = incident.predictedExit;
  $('#intel-location').textContent = exit.name;
  $('#intel-channel').textContent = exit.type;
  $('#intel-radius').textContent = `${exit.radiusMeters} m`;
  $('#intel-landmark').textContent = exit.landmark || exit.address;
  $('#intel-suspect').textContent = exit.suspectToken || 'TOKEN NOT AVAILABLE';
  $('#intel-confidence').textContent = `${Math.round(incident.confidence)}%`;
  $('#graph-target-id').textContent = `#${incident.id}`;
  $('#dispatch-button-sub').textContent = `${incident.patrol.unitId} · ${incident.patrol.state || 'STANDBY'}`;
  const holdSub = $('#hold-button small');
  if (holdSub) holdSub.textContent = incident.switchHoldState === 'NOT REQUESTED' ? 'Simulation only · no bank connection' : `Demo state: ${incident.switchHoldState}`;
  $('#dispatch-button b').textContent = incident.patrol.state === 'EN ROUTE' ? 'PCR PATROL DISPATCHED' : 'DISPATCH NEAREST PCR PATROL';
  $('#dispatch-button').classList.toggle('is-dispatched', incident.patrol.state === 'EN ROUTE');
  if (incident.demoPhase) {
    let phase = $('.demo-phase-line');
    if (!phase) {
      phase = document.createElement('div');
      phase.className = 'demo-phase-line';
      $('.intel-section').append(phase);
    }
    phase.replaceChildren();
    const span = document.createElement('span'); span.textContent = 'SCRIPTED SCENARIO';
    const value = document.createElement('strong'); value.textContent = incident.demoPhase;
    phase.append(span, value);
  } else {
    $('.demo-phase-line')?.remove();
  }
}

async function selectIncident(id, options = {}) {
  const incident = state.incidents.find((item) => item.id === id);
  if (!incident) return;
  state.selectedId = id;
  renderFeed();
  renderKpis();
  renderIntel(incident);
  renderMuleGraph(incident);
  updateMapLabels(incident);
  renderIncidentOnMap(incident, { fit: options.fit !== false, remainingSeconds: getRemainingSeconds(incident) });
  if (options.reason === 'manual selection') addLog(`Selected ${incident.id}; map and graph synchronized.`, 'data');

  // If this is a live backend case and network hasn't been fetched yet
  if (incident.dbId && runtimeConfig.apiBaseUrl && !incident.networkLoaded) {
    try {
      const network = await fetchCaseNetwork(incident.dbId, runtimeConfig);
      if (network && network.edges && network.edges.length > 0) {
        incident.networkLoaded = true;
        const mapped = mapCaseToIncident(
          { id: incident.dbId, case_number: incident.id, reported_amount: incident.amountINR, category: incident.fraudType, status: incident.status, victim_district: incident.city, victim_state: incident.state },
          null,
          network,
          incident.prediction
        );
        incident.transactionPath = mapped.transactionPath;
        renderMuleGraph(incident);
      }
    } catch (netErr) {
      console.warn('Network graph fetch warning for case:', netErr);
    }
  }
}

function updateClock() {
  const now = new Date();
  $('#clock-ist').textContent = IST_FORMATTER.format(now);
  $('#clock-utc').textContent = UTC_FORMATTER.format(now);
}

function refreshCountdowns() {
  updateLiveCountdowns(state.incidents);
  const selected = currentIncident();
  if (selected) {
    const remaining = getRemainingSeconds(selected);
    const timer = $('#map-countdown-overlay');
    if (timer) timer.textContent = remaining > 0 ? `T− ${formatCountdown(remaining)}` : 'T− 00:00';
    const windowLabel = $('#map-window-state');
    if (windowLabel) windowLabel.textContent = remaining <= 0 ? 'WINDOW EXPIRED' : remaining <= 900 ? 'CRITICAL WINDOW' : 'INTERCEPTABLE';
    const eta = selected.patrol.etaDeadlineMs ? Math.max(0, Math.ceil((selected.patrol.etaDeadlineMs - Date.now()) / 1000)) : null;
    if (selected.patrol.state === 'EN ROUTE' && eta !== null) {
      $('#dispatch-button-sub').textContent = `${selected.patrol.unitId} · ETA ${formatCountdown(eta)}`;
    }
    renderKpis();
    if (selected.patrol.state === 'EN ROUTE' && eta === 0 && !selected.patrol.arrivalLogged) {
      selected.patrol.arrivalLogged = true;
      selected.patrol.state = 'ON SCENE (SIM)';
      renderIntel(selected);
      $('#map-unit-state').textContent = selected.patrol.state;
      addLog(`SIMULATION: ${selected.patrol.unitId} reached the assigned demo zone (ETA elapsed).`, 'dispatch');
      showToast(`${selected.patrol.unitId} marked on scene in simulation.`, 'success');
    }
  }
  const now = Date.now();
  for (const incident of state.incidents) {
    const remaining = getRemainingSeconds(incident, now);
    const previous = state.lastShownThresholds.get(incident.id);
    const bucket = remaining <= 0 ? 'expired' : remaining <= 900 ? 'critical' : 'normal';
    if (previous && previous !== bucket) {
      state.lastShownThresholds.set(incident.id, bucket);
      if (incident.id === state.selectedId) selectIncident(incident.id, { fit: false });
      else if (state.filter === 'critical' || previous === 'critical' || bucket === 'expired') renderFeed();
      if (bucket === 'expired') addLog(`${incident.id}: model countdown elapsed; forecast window expired.`, 'warning');
      else if (bucket === 'critical') addLog(`${incident.id}: entered the 15-minute critical threshold.`, 'warning');
    } else if (!previous) state.lastShownThresholds.set(incident.id, bucket);
  }
}

function makeDialogButton(label, className, action) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `dialog-action-button ${className || ''}`.trim();
  button.textContent = label;
  button.addEventListener('click', action);
  return button;
}

function closeDialog() {
  const dialog = $('#action-dialog');
  if (dialog.open) dialog.close();
}

function openDialog({ title, eyebrow = 'ACTION / SIMULATION', content, actions = [] }) {
  const dialog = $('#action-dialog');
  $('#dialog-title').textContent = title;
  $('#dialog-eyebrow').textContent = eyebrow;
  const contentRoot = $('#dialog-content');
  contentRoot.replaceChildren();
  if (content instanceof Node) contentRoot.append(content);
  else contentRoot.textContent = String(content ?? '');
  const actionsRoot = $('#dialog-actions');
  actionsRoot.replaceChildren();
  actions.forEach((action) => actionsRoot.append(makeDialogButton(action.label, action.className, action.onClick)));
  if (!dialog.open) dialog.showModal();
}

function makeTable(rows) {
  const table = document.createElement('table');
  table.className = 'dialog-table';
  const body = document.createElement('tbody');
  rows.forEach(([label, value]) => {
    const row = document.createElement('tr');
    const heading = document.createElement('th'); heading.scope = 'row'; heading.textContent = label;
    const cell = document.createElement('td'); cell.textContent = String(value ?? '—');
    row.append(heading, cell); body.append(row);
  });
  table.append(body);
  return table;
}

function dispatchPatrol(incident, { silent = false, source = 'operator action' } = {}) {
  if (incident.patrol.state === 'EN ROUTE' || incident.patrol.state === 'ON SCENE (SIM)') {
    if (!silent) showToast(`${incident.patrol.unitId} is already assigned to this demo incident.`, 'warning');
    return false;
  }
  incident.patrol.state = 'EN ROUTE';
  incident.patrol.dispatchTimestamp = new Date().toISOString();
  incident.patrol.etaDeadlineMs = Date.now() + (Number(incident.patrol.etaMinutes) || 4) * 60 * 1000;
  incident.patrol.arrivalLogged = false;
  addLog(`SIMULATION: ${incident.patrol.unitId} dispatched to ${incident.predictedExit.name} by ${source}; ETA ${Number(incident.patrol.etaMinutes).toFixed(1)} min.`, 'dispatch');
  renderIntel(incident);
  updateMapLabels(incident);
  renderIncidentOnMap(incident, { fit: true, remainingSeconds: getRemainingSeconds(incident) });
  if (!silent) showToast(`${incident.patrol.unitId} set EN ROUTE in simulation.`, 'success');
  return true;
}

function requestDispatch() {
  const incident = currentIncident();
  if (!incident) return;
  if (incident.patrol.state === 'EN ROUTE' || incident.patrol.state === 'ON SCENE (SIM)') {
    showToast(`${incident.patrol.unitId} is already ${incident.patrol.state.toLowerCase()}.`, 'warning');
    return;
  }
  openDialog({
    title: 'Confirm patrol dispatch',
    eyebrow: 'PCR / LOCAL SIMULATION ONLY',
    content: makeTable([
      ['Incident', `#${incident.id}`],
      ['Assigned unit', incident.patrol.unitId],
      ['Forecast destination', incident.predictedExit.name],
      ['Destination coordinates', `${incident.predictedExit.lat.toFixed(5)}, ${incident.predictedExit.lon.toFixed(5)}`],
      ['Estimated ETA', `${Number(incident.patrol.etaMinutes).toFixed(1)} min (model estimate)`],
      ['Current status', incident.patrol.state || 'STANDBY']
    ]),
    actions: [
      { label: 'CANCEL', onClick: closeDialog },
      { label: 'CONFIRM SIMULATED DISPATCH', className: 'dialog-action-primary', onClick: () => { closeDialog(); dispatchPatrol(incident, { source: 'operator confirmation' }); } }
    ]
  });
}

function requestSwitchHold() {
  const incident = currentIncident();
  if (!incident) return;
  const requestId = `SIM-HOLD-${Date.now().toString(36).toUpperCase()}`;
  openDialog({
    title: 'ATM switch velocity-hold request',
    eyebrow: 'SIMULATED OUTBOUND MESSAGE',
    content: (() => {
      const wrap = document.createElement('div');
      wrap.append(makeTable([
        ['Request ID', requestId],
        ['Incident', `#${incident.id}`],
        ['Destination facility', incident.predictedExit.facilityId || 'DEMO-FACILITY'],
        ['Requested control', 'Review / temporary velocity hold'],
        ['Target amount', formatMoney(incident.amountINR)],
        ['Transport', 'NOT CONNECTED — local simulation'],
        ['Current demo state', incident.switchHoldState]
      ]));
      const note = document.createElement('p');
      note.className = 'dialog-note';
      note.textContent = 'This action will not contact a bank, switch, NPCI, or law-enforcement service. Confirming it records a simulated acknowledgement in this browser session only.';
      wrap.append(note);
      return wrap;
    })(),
    actions: [
      { label: 'CANCEL', onClick: closeDialog },
      { label: 'SIMULATE HOLD ACK', className: 'dialog-action-warning', onClick: () => {
        closeDialog();
        incident.switchHoldState = 'SIMULATED ACK';
        incident.switchHoldRequestId = requestId;
        addLog(`SIMULATION: switch hold request ${requestId} received a simulated acknowledgement; no external message sent.`, 'warning');
        renderIntel(incident);
        showToast('Switch hold acknowledgement simulated locally; no bank connection.', 'warning');
      } }
    ]
  });
}

function buildAdvisorySheet(incident) {
  const sheet = document.createElement('section');
  sheet.className = 'advisory-sheet';
  const heading = document.createElement('h3'); heading.textContent = 'TACTICAL DISPATCH ADVISORY';
  const sub = document.createElement('div'); sub.className = 'advisory-sub'; sub.textContent = `CYBER-TRAC v4.2 · GENERATED ${new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'medium' })} IST · SIMULATED INTELLIGENCE`;
  sheet.append(heading, sub);
  const table = document.createElement('table');
  const body = document.createElement('tbody');
  const rows = [
    ['Incident reference', incident.id], ['City / sector', `${incident.area}, ${incident.city}, ${incident.state}`], ['Fraud modality', incident.fraudType],
    ['Reported / suspected exposure', formatMoney(incident.amountINR)], ['Predicted cash-out site', incident.predictedExit.name], ['Facility identifier', incident.predictedExit.facilityId || 'Not supplied'],
    ['Facility coordinates', `${incident.predictedExit.lat.toFixed(6)}, ${incident.predictedExit.lon.toFixed(6)}`], ['Channel', incident.predictedExit.type],
    ['Forecast radius', `${incident.predictedExit.radiusMeters} metres (model estimate)`], ['Spatial confidence', `${incident.confidence}% (model estimate)`],
    ['Golden-window countdown', formatCountdown(getRemainingSeconds(incident))], ['Mule network correlation', incident.muleRingLinked ? 'Linked in synthetic graph' : 'Not confirmed'],
    ['Suggested unit', `${incident.patrol.unitId} · ${incident.patrol.state || 'STANDBY'}`], ['Unit ETA', incident.patrol.etaDeadlineMs ? `${formatCountdown(Math.max(0, Math.ceil((incident.patrol.etaDeadlineMs - Date.now()) / 1000)))} remaining` : `${Number(incident.patrol.etaMinutes).toFixed(1)} min estimate`],
    ['Suspect token', incident.predictedExit.suspectToken || 'Not available'], ['Switch-hold demo state', incident.switchHoldState]
  ];
  rows.forEach(([label, value]) => { const tr = document.createElement('tr'); const th = document.createElement('th'); th.textContent = label; const td = document.createElement('td'); td.textContent = value; tr.append(th, td); body.append(tr); });
  table.append(body); sheet.append(table);
  const warning = document.createElement('div'); warning.className = 'advisory-warning'; warning.textContent = 'IMPORTANT: This is a synthetic forecasting demonstration, not a confirmed incident location or a verified dispatch order. Independently validate the evidence and destination through authorized channels before any real-world action.';
  sheet.append(warning);
  const footer = document.createElement('p'); footer.style.cssText = 'margin:10px 0 0;color:#475569;font:9px ui-monospace,monospace'; footer.textContent = 'CYBER-TRAC DEMO · LinuxONE s390x interface prototype · No live NCRP, bank, or police systems connected.';
  sheet.append(footer);
  return sheet;
}

function requestAdvisory() {
  const incident = currentIncident();
  if (!incident) return;
  const sheet = buildAdvisorySheet(incident);
  openDialog({
    title: 'Tactical dispatch advisory',
    eyebrow: 'DOCUMENT / PRINT PREVIEW',
    content: sheet,
    actions: [
      { label: 'CLOSE', onClick: closeDialog },
      { label: 'PRINT ADVISORY', className: 'dialog-action-primary', onClick: () => window.print() }
    ]
  });
}

async function triggerScenario() {
  if (state.scenarioRunning) return;
  state.scenarioRunning = true;
  const button = $('#scenario-button');
  button.disabled = true;
  const originalText = button.textContent;
  button.setAttribute('aria-busy', 'true');
  try {
    const incident = normalizedIncident(createScenarioIncident());
    state.incidents.unshift(incident);
    state.filter = 'all';
    state.search = '';
    $('#incident-search').value = '';
    $$('[data-filter]').forEach((buttonEl) => {
      const isActive = buttonEl.dataset.filter === 'all';
      buttonEl.classList.toggle('is-active', isActive);
      buttonEl.setAttribute('aria-pressed', String(isActive));
    });
    addLog(`SIMULATION: scripted attack scenario ${incident.id} injected into local feed.`, 'demo');
    selectIncident(incident.id, { fit: true, scenarioStep: true });
    showToast('Scripted high-value complaint injected. Scenario sequence starting.', 'warning');
    await runScenarioSteps({
      incident,
      selectIncident: (id, options) => selectIncident(id, options),
      dispatchPatrol: (target, options) => dispatchPatrol(target, options),
      addLog,
      toast: (message, kind) => showToast(message, kind)
    });
    showToast('Scenario complete: trace, hotspot and demo patrol state are visible.', 'success');
  } catch (error) {
    console.error('Scenario playback failed.', error);
    showToast('Scenario playback interrupted. See browser console for details.', 'warning');
  } finally {
    state.scenarioRunning = false;
    button.disabled = false;
    button.removeAttribute('aria-busy');
    // Keep the authored label stable for subsequent replay.
    if (button.textContent !== originalText) button.textContent = originalText;
  }
}

function isValidIncidentRecord(record) {
  return Boolean(record && typeof record.id === 'string' && record.id.length <= 80 &&
    typeof record.city === 'string' && typeof record.fraudType === 'string' &&
    Number.isFinite(Number(record.amountINR)) && Number.isFinite(Number(record.confidence)) &&
    record.source && Number.isFinite(Number(record.source.lat)) && Number.isFinite(Number(record.source.lon)) &&
    record.predictedExit && Number.isFinite(Number(record.predictedExit.lat)) && Number.isFinite(Number(record.predictedExit.lon)) &&
    record.patrol && typeof record.patrol.unitId === 'string');
}

function handleTelemetryMessage(message) {
  if (!message || typeof message !== 'object' || typeof message.type !== 'string') return;
  if (message.type === 'telemetry') {
    const latency = Number(message.latencyMs);
    if (Number.isFinite(latency) && latency >= 0 && latency < 10000) $('#latency-value').textContent = `${latency.toFixed(1)} ms`;
    return;
  }
  if (message.type === 'incident.remove' && typeof message.id === 'string') {
    state.incidents = state.incidents.filter((incident) => incident.id !== message.id);
    if (state.selectedId === message.id) state.selectedId = state.incidents[0]?.id ?? null;
    renderFeed();
    const selected = currentIncident();
    if (selected) selectIncident(selected.id, { fit: true });
    addLog(`Live feed marked ${message.id} removed from this view.`, 'data');
    return;
  }
  if (message.type === 'incident.upsert' || message.type === 'incident.update') {
    if (!isValidIncidentRecord(message.incident)) {
      addLog('Rejected malformed incident update from telemetry feed.', 'warning');
      return;
    }
    const incoming = normalizedIncident(message.incident);
    const existingIndex = state.incidents.findIndex((item) => item.id === incoming.id);
    if (existingIndex >= 0) state.incidents.splice(existingIndex, 1, incoming);
    else state.incidents.unshift(incoming);
    state.lastShownThresholds.set(incoming.id, getRemainingSeconds(incoming) <= 900 ? 'critical' : 'normal');
    renderFeed();
    renderKpis();
    if (state.selectedId === incoming.id || existingIndex < 0) selectIncident(incoming.id, { fit: true });
    addLog(`Live feed ${existingIndex >= 0 ? 'updated' : 'added'} ${incoming.id}.`, 'data');
    showToast(`Live incident feed ${existingIndex >= 0 ? 'updated' : 'added'}: ${incoming.id}`, 'success');
  }
}

async function executeMLPrediction() {
  const incident = currentIncident();
  if (!incident) {
    showToast('Select a case record before running ML prediction.', 'warning');
    return;
  }

  const btn = $('#run-prediction-button');
  if (!btn) return;
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.style.opacity = '0.7';
  const versionSub = $('#prediction-model-version');
  if (versionSub) versionSub.textContent = 'Executing Worker 2 ML inference pipeline...';
  addLog(`Initiating ML cash-withdrawal inference for #${incident.id} (case ID: ${incident.dbId || 1})...`, 'data');

  try {
    const payload = {
      case_id: incident.dbId || 1,
      reported_amount: Number(incident.amountINR) || 150000,
      source_channel: 'UPI'
    };

    const result = await requestPrediction(payload, runtimeConfig);
    addLog(`ML INFERENCE SUCCESS: Prediction ${result.prediction_id} generated. Model: ${result.model_version}. Risk: ${result.risk_level.toUpperCase()} (${(result.risk_score * 100).toFixed(1)}%).`, 'dispatch');

    incident.prediction = result;
    incident.confidence = Math.round(result.risk_score * 100);
    incident.riskLevel = result.risk_level;

    if (result.candidate_locations && result.candidate_locations.length > 0) {
      const topCand = result.candidate_locations[0];
      incident.predictedExit = {
        name: topCand.name,
        type: 'BANK ATM / CSP CLUSTER',
        bank: `${topCand.district} Network Hub`,
        address: `${topCand.district}, ${topCand.state}`,
        landmark: topCand.disclaimer || `Forecast Cluster in ${topCand.district}`,
        lat: topCand.latitude,
        lon: topCand.longitude,
        radiusMeters: 240,
        etaMinutes: 4.0,
        suspectToken: 'CARD •••• 3301',
        facilityId: `LOC-PRED-${result.prediction_id.slice(-4)}`
      };
      incident.patrol.lat = topCand.latitude + 0.007;
      incident.patrol.lon = topCand.longitude - 0.008;
      incident.cashpoints = [
        { id: 'CP-01', type: 'ATM', name: `${topCand.name} (Predicted Primary)`, lat: topCand.latitude, lon: topCand.longitude },
        { id: 'CP-02', type: 'ATM', name: `Nearby ATM Cluster (${topCand.district})`, lat: topCand.latitude + 0.004, lon: topCand.longitude - 0.003 },
        { id: 'CP-03', type: 'CSP', name: `Nearby CSP Point (${topCand.district})`, lat: topCand.latitude - 0.003, lon: topCand.longitude + 0.004 }
      ];
    }

    renderIntel(incident);
    updateMapLabels(incident);
    renderIncidentOnMap(incident, { fit: true, remainingSeconds: getRemainingSeconds(incident) });
    renderFeed();
    renderKpis();

    openDialog({
      title: 'ML Predictive Cash-Out Inference Result',
      eyebrow: 'WORKER 2 ML PIPELINE / s390x CPACF ACCELERATED',
      content: makeTable([
        ['Prediction ID', result.prediction_id],
        ['Case Reference', `#${incident.id} (DB ID: ${result.case_id})`],
        ['ML Model Version', `${result.model_version} (Scikit-learn / LinuxONE)`],
        ['Assessed Risk Level', `${result.risk_level.toUpperCase()} (Score: ${(result.risk_score * 100).toFixed(1)}%)`],
        ['Primary Exit Hotspot', incident.predictedExit.name],
        ['Coordinates', `${incident.predictedExit.lat.toFixed(5)}° N, ${incident.predictedExit.lon.toFixed(5)}° E`],
        ['Reporting Delay', result.reporting_delay_hours != null ? `${result.reporting_delay_hours.toFixed(1)} hours` : '0.5 hours (immediate)'],
        ['Ranked Candidates', (result.candidate_locations || []).map((c) => `${c.name} (${(c.confidence_score * 100).toFixed(1)}%)`).join(', ')],
        ['Key Risk Factors', (result.key_risk_factors || []).join(', ') || 'Rapid inter-bank layering, flagged mule node'],
        ['Mandatory Disclaimer', result.disclaimer || 'Probabilistic estimate for tactical investigative guidance only.']
      ]),
      actions: [
        { label: 'CLOSE', onClick: closeDialog },
        { label: 'RE-CENTER MAP TO PREDICTION', className: 'dialog-action-primary', onClick: () => { closeDialog(); recenterMap(); } }
      ]
    });

    showToast(`ML Prediction complete: #${incident.id} assessed as ${result.risk_level.toUpperCase()}`, 'success');
  } catch (error) {
    console.error('ML Prediction failed:', error);
    addLog(`ML INFERENCE FAILED: ${error.message}`, 'warning');
    showToast(`ML Inference Failed: ${error.message}`, 'warning');
  } finally {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.innerHTML = originalHtml;
  }
}

function bindControls() {
  $$('[data-filter]').forEach((button) => button.addEventListener('click', () => {
    state.filter = button.dataset.filter;
    $$('[data-filter]').forEach((candidate) => {
      const active = candidate === button;
      candidate.classList.toggle('is-active', active);
      candidate.setAttribute('aria-pressed', String(active));
    });
    renderFeed();
  }));
  $('#incident-search').addEventListener('input', (event) => { state.search = event.target.value; renderFeed(); });
  $('#clear-search').addEventListener('click', () => { state.search = ''; $('#incident-search').value = ''; renderFeed(); $('#incident-search').focus(); });
  $('#recenter-map').addEventListener('click', () => { recenterMap(); showToast('Map recentered to selected incident.', 'info'); });
  $('#dispatch-button').addEventListener('click', requestDispatch);
  $('#hold-button').addEventListener('click', requestSwitchHold);
  $('#advisory-button').addEventListener('click', requestAdvisory);
  $('#scenario-button').addEventListener('click', triggerScenario);
  $('#run-prediction-button')?.addEventListener('click', executeMLPrediction);
  $('#clear-log').addEventListener('click', () => { $('#event-log').replaceChildren(); addLog('Event log view cleared by operator.', 'data'); });
  $('#dialog-close').addEventListener('click', closeDialog);
  $('#action-dialog').addEventListener('click', (event) => { if (event.target === $('#action-dialog')) closeDialog(); });
}

async function initialize() {
  initMap();
  bindControls();
  updateClock();
  window.setInterval(updateClock, 1000);
  state.incidents = await loadIncidents();
  state.selectedId = state.incidents[0]?.id ?? null;
  state.incidents.forEach((incident) => state.lastShownThresholds.set(incident.id, getRemainingSeconds(incident) <= 900 ? 'critical' : 'normal'));
  renderFeed();
  const selected = currentIncident();
  if (selected) selectIncident(selected.id, { fit: true });
  $('#last-ingest').textContent = `LAST INGEST — ${IST_FORMATTER.format(new Date())} IST`;
  addLog('Tactical console ready. All visible records and telemetry are synthetic.', 'data');
  window.setInterval(refreshCountdowns, 1000);
  if (runtimeConfig.webSocketUrl) {
    connectTelemetry({
      url: runtimeConfig.webSocketUrl,
      onStatus: (status, detail) => {
        const label = $('#stream-label');
        const stream = $('.stream-state');
        const names = { connecting: 'STREAM CONNECTING', connected: 'STREAM ACTIVE', reconnecting: 'STREAM RECONNECTING', disconnected: 'STREAM OFFLINE', degraded: 'STREAM DEGRADED', error: 'STREAM CONFIG ERROR', 'message-error': 'STREAM DATA ERROR' };
        label.textContent = names[status] || 'STREAM STATUS UNKNOWN';
        stream.classList.toggle('is-degraded', status !== 'connected');
        if (detail) addLog(`Telemetry: ${detail}`, 'warning');
      },
      onMessage: (message) => handleTelemetryMessage(message)
    });
  }
  // Operational actions intentionally remain simulation-only until an authenticated, authorized API contract is implemented.
}

initialize().catch((error) => {
  console.error('Console initialization failed.', error);
  const list = $('#incident-list');
  if (list) {
    const message = document.createElement('div');
    message.className = 'empty-state';
    message.textContent = 'Console initialization failed. Reload the page or inspect the browser console.';
    list.replaceChildren(message);
  }
  showToast('Initialization failed.', 'warning');
});
