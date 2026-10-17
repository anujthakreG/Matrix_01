/*
 * MATRIX Intel API Client — Backend Integration seam for IBM LinuxONE / FastAPI.
 * Secure, session/token friendly, CORS-compatible.
 */

const DEFAULT_CONFIG = Object.freeze({
  apiBaseUrl: '',
  casesPath: '/api/v1/cases',
  incidentsPath: '/api/v1/cases',
  summaryPath: '/api/v1/dashboard/summary',
  predictionsPath: '/api/v1/predictions',
  healthPath: '/api/v1/health',
  networkPath: '/api/v1/transactions',
  webSocketUrl: ''
});

export function getRuntimeConfig() {
  const supplied = window.CYBER_TRAC_CONFIG && typeof window.CYBER_TRAC_CONFIG === 'object'
    ? window.CYBER_TRAC_CONFIG
    : {};
  const config = { ...DEFAULT_CONFIG, ...supplied };

  if (!config.apiBaseUrl && typeof window !== 'undefined' && window.location) {
    if (window.location.port === '8000') {
      config.apiBaseUrl = window.location.origin;
    } else if (window.location.hostname) {
      config.apiBaseUrl = `${window.location.protocol}//${window.location.hostname}:8000`;
    }
  }
  return config;
}

function validateEndpoint(endpoint) {
  if (endpoint.protocol !== 'http:' && endpoint.protocol !== 'https:') {
    throw new Error(`Unsupported API protocol: ${endpoint.protocol}`);
  }
}

function validateEnvelope(payload) {
  if (Array.isArray(payload)) return payload;
  const records = payload?.records || payload?.incidents || payload?.items;
  if (Array.isArray(records)) return records;
  throw new Error('API response must be an array or an object with records/incidents/items.');
}

/**
 * Health check endpoint: verifies DB and ML pipeline connectivity.
 */
export async function fetchHealth(config = getRuntimeConfig()) {
  if (!config.apiBaseUrl) return null;
  const base = new URL(config.apiBaseUrl, window.location.href);
  const endpoint = new URL(config.healthPath || '/api/v1/health', base);
  validateEndpoint(endpoint);
  const response = await fetch(endpoint, {
    method: 'GET',
    mode: 'cors',
    cache: 'no-store',
    headers: { Accept: 'application/json' }
  });
  if (!response.ok) throw new Error(`Health check returned HTTP ${response.status}`);
  return await response.json();
}

/**
 * Executive dashboard summary metrics directly from verified database records.
 */
export async function fetchDashboardSummary(config = getRuntimeConfig()) {
  if (!config.apiBaseUrl) return null;
  const base = new URL(config.apiBaseUrl, window.location.href);
  const endpoint = new URL(config.summaryPath || '/api/v1/dashboard/summary', base);
  validateEndpoint(endpoint);
  const response = await fetch(endpoint, {
    method: 'GET',
    mode: 'cors',
    cache: 'no-store',
    headers: { Accept: 'application/json' }
  });
  if (!response.ok) throw new Error(`Dashboard summary returned HTTP ${response.status}`);
  return await response.json();
}

/**
 * Fetches verified cybercrime cases from FastAPI backend.
 */
export async function fetchLiveIncidents(config = getRuntimeConfig()) {
  if (!config.apiBaseUrl) return null;
  const base = new URL(config.apiBaseUrl, window.location.href);
  const endpoint = new URL(config.casesPath || config.incidentsPath || '/api/v1/cases', base);
  validateEndpoint(endpoint);

  const response = await fetch(endpoint, {
    method: 'GET',
    mode: 'cors',
    credentials: endpoint.origin === window.location.origin ? 'same-origin' : 'include',
    cache: 'no-store',
    headers: { Accept: 'application/json' }
  });
  if (!response.ok) throw new Error(`Live incidents endpoint responded with HTTP ${response.status}.`);
  const data = await response.json();
  return validateEnvelope(data);
}

/**
 * Fetches case details including associated transactions and locations.
 */
export async function fetchCaseDetail(caseId, config = getRuntimeConfig()) {
  if (!config.apiBaseUrl || !caseId) return null;
  const base = new URL(config.apiBaseUrl, window.location.href);
  const endpoint = new URL(`/api/v1/cases/${caseId}`, base);
  validateEndpoint(endpoint);
  const response = await fetch(endpoint, {
    method: 'GET',
    mode: 'cors',
    cache: 'no-store',
    headers: { Accept: 'application/json' }
  });
  if (!response.ok) return null;
  return await response.json();
}

/**
 * Fetches transaction network graph topology for a given case.
 */
export async function fetchCaseNetwork(caseId, config = getRuntimeConfig()) {
  if (!config.apiBaseUrl || !caseId) return null;
  const base = new URL(config.apiBaseUrl, window.location.href);
  const endpoint = new URL(`/api/v1/transactions/${caseId}/network`, base);
  validateEndpoint(endpoint);
  const response = await fetch(endpoint, {
    method: 'GET',
    mode: 'cors',
    cache: 'no-store',
    headers: { Accept: 'application/json' }
  });
  if (!response.ok) return null;
  return await response.json();
}

/**
 * Executes ML predictive cash-withdrawal inference pipeline via POST /api/v1/predictions.
 */
export async function requestPrediction(payload, config = getRuntimeConfig()) {
  if (!config.apiBaseUrl) throw new Error('API base URL not configured.');
  const base = new URL(config.apiBaseUrl, window.location.href);
  const endpoint = new URL(config.predictionsPath || '/api/v1/predictions', base);
  validateEndpoint(endpoint);

  const response = await fetch(endpoint, {
    method: 'POST',
    mode: 'cors',
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json'
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message = errorBody?.detail || errorBody?.message || `Inference request failed with HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.data = errorBody;
    throw error;
  }
  return await response.json();
}

/**
 * Maps a backend Case record into the frontend's rich tactical incident schema.
 */
export function mapCaseToIncident(caseItem, detail = null, network = null, prediction = null) {
  const id = caseItem.case_number || `SYN-CASE-${caseItem.id}`;
  const reportedAmount = Number(caseItem.reported_amount) || 0;

  const incidentDate = caseItem.incident_date ? new Date(caseItem.incident_date) : new Date();
  const reportedAt = caseItem.reported_at ? new Date(caseItem.reported_at) : new Date();
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - incidentDate.getTime()) / 1000));
  // Keep an active 30-minute triage golden window for demonstration
  const remainingSeconds = Math.max(0, 1800 - (elapsedSeconds % 1800));

  let sourceLat = 28.6315;
  let sourceLon = 77.2167;
  let sourceLabel = `${caseItem.victim_district || 'New Delhi'}, ${caseItem.victim_state || 'Delhi'}`;

  let predictedExit = {
    name: 'Sector 18 ATM Hub (Candidate Withdrawal)',
    type: 'BANK ATM',
    bank: 'Axis / SBI Network',
    address: 'Sector 18 Commercial Pocket, Noida / NCR',
    landmark: 'Near Sector 18 Commercial Hub & Metro Entrance',
    lat: 28.5708,
    lon: 77.3271,
    radiusMeters: 280,
    etaMinutes: 4.2,
    suspectToken: 'CARD •••• 3301',
    facilityId: 'LOC-ATM-02'
  };

  if (detail?.locations && detail.locations.length > 0) {
    const originLoc = detail.locations.find((l) => l.location_type === 'reported') || detail.locations[0];
    sourceLat = originLoc.latitude;
    sourceLon = originLoc.longitude;
    sourceLabel = originLoc.name || sourceLabel;

    const exitLoc = detail.locations.find((l) => l.location_type === 'candidate_withdrawal' || l.location_type === 'confirmed_withdrawal');
    if (exitLoc) {
      predictedExit.name = exitLoc.name;
      predictedExit.lat = exitLoc.latitude;
      predictedExit.lon = exitLoc.longitude;
      predictedExit.address = `${exitLoc.district || 'NCR'}, ${exitLoc.state || ''}`;
      predictedExit.landmark = exitLoc.name;
      predictedExit.facilityId = `LOC-${exitLoc.id || 'ATM'}`;
    }
  }

  if (prediction?.candidate_locations && prediction.candidate_locations.length > 0) {
    const topCand = prediction.candidate_locations[0];
    predictedExit.name = topCand.name;
    predictedExit.lat = topCand.latitude;
    predictedExit.lon = topCand.longitude;
    predictedExit.address = `${topCand.district}, ${topCand.state}`;
    predictedExit.landmark = topCand.disclaimer || `Forecast cluster: ${topCand.district}`;
    predictedExit.radiusMeters = 240;
    predictedExit.confidence = Math.round(topCand.confidence_score * 100);
  }

  // Construct transaction path for Mule Graph visualization
  let transactionPath = [];
  if (network && network.edges && network.edges.length > 0) {
    const nodeMap = new Map((network.nodes || []).map((n) => [n.id, n]));
    const firstEdge = network.edges[0];
    const sourceNode = nodeMap.get(firstEdge.source);

    transactionPath.push({
      id: firstEdge.source,
      label: 'VICTIM',
      bank: sourceNode?.label || firstEdge.source,
      role: 'Victim account',
      amountINR: reportedAmount
    });

    network.edges.forEach((edge, idx) => {
      const targetNode = nodeMap.get(edge.target);
      const isLast = idx === network.edges.length - 1;
      transactionPath.push({
        id: edge.target,
        label: isLast ? 'TIER-2 MULE' : `TIER-${idx + 1} MULE`,
        bank: targetNode?.label || edge.target,
        role: targetNode?.node_type || 'Mule account',
        amountINR: edge.amount
      });
    });

    transactionPath.push({
      id: 'exit-predicted',
      label: 'FLAGGED EXIT',
      bank: predictedExit.name,
      role: 'Predicted cash-out',
      amountINR: network.edges[network.edges.length - 1].amount
    });
  } else if (detail?.transactions && detail.transactions.length > 0) {
    transactionPath.push({
      id: 'v1',
      label: 'VICTIM',
      bank: detail.transactions[0].sender_account,
      role: 'Victim account',
      amountINR: reportedAmount
    });
    detail.transactions.forEach((tx, idx) => {
      transactionPath.push({
        id: `m${idx + 1}`,
        label: `TIER-${idx + 1} MULE`,
        bank: `${tx.receiver_account} (${tx.channel})`,
        role: 'Mule account',
        amountINR: tx.amount
      });
    });
    transactionPath.push({
      id: 'exit-predicted',
      label: 'FLAGGED EXIT',
      bank: predictedExit.name,
      role: 'Predicted cash-out',
      amountINR: detail.transactions[detail.transactions.length - 1].amount
    });
  }

  const confidence = prediction
    ? Math.round((prediction.risk_score || 0.85) * 100)
    : 85;

  return {
    id: id,
    dbId: caseItem.id,
    city: caseItem.victim_district || 'New Delhi',
    state: caseItem.victim_state || 'Delhi',
    area: caseItem.victim_district || 'Connaught Place',
    fraudType: caseItem.category ? caseItem.category.toUpperCase().replace(/_/g, ' ') : 'UNAUTHORIZED TRANSFER',
    amountINR: reportedAmount,
    remainingSeconds: remainingSeconds,
    confidence: confidence,
    muleRingLinked: (caseItem.transactions_count || (detail?.transactions?.length ?? 0)) > 0,
    complaintReceived: reportedAt.toLocaleTimeString('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' IST',
    status: (caseItem.status || 'OPEN').toUpperCase(),
    isLiveBackend: true,
    source: {
      lat: sourceLat,
      lon: sourceLon,
      label: sourceLabel
    },
    predictedExit: predictedExit,
    patrol: {
      unitId: 'PCR-DL-01',
      lat: predictedExit.lat + 0.007,
      lon: predictedExit.lon - 0.008,
      etaMinutes: 4.2,
      state: 'STANDBY'
    },
    cashpoints: [
      { id: 'CP-01', type: 'ATM', name: `${predictedExit.name} (flagged)`, lat: predictedExit.lat, lon: predictedExit.lon },
      { id: 'CP-02', type: 'ATM', name: 'Nearby Bank ATM (Sector 18)', lat: predictedExit.lat + 0.003, lon: predictedExit.lon - 0.004 },
      { id: 'CP-03', type: 'CSP', name: 'AEPS Banking Kiosk Hub', lat: predictedExit.lat - 0.003, lon: predictedExit.lon + 0.003 }
    ],
    transactionPath: transactionPath,
    analystNote: `Verified case record ${id} loaded from MATRIX Intel backend database.`
  };
}

/**
 * Connects to a configured telemetry socket and reconnects with capped exponential backoff.
 */
export function connectTelemetry({ url, onStatus = () => {}, onMessage = () => {} }) {
  if (!url) return () => {};
  let socket = null;
  let retryTimer = null;
  let stopped = false;
  let attempts = 0;
  const endpoint = new URL(url, window.location.href);
  if (window.location.protocol === 'https:' && endpoint.protocol !== 'wss:') {
    onStatus('error', 'Secure pages require a wss:// telemetry endpoint.');
    return () => {};
  }

  const connect = () => {
    if (stopped) return;
    onStatus(attempts ? 'reconnecting' : 'connecting');
    try {
      socket = new WebSocket(endpoint);
      socket.addEventListener('open', () => { attempts = 0; onStatus('connected'); });
      socket.addEventListener('message', (event) => {
        if (typeof event.data !== 'string' || event.data.length > 512_000) return;
        try { onMessage(JSON.parse(event.data)); }
        catch { onStatus('message-error', 'Ignored malformed telemetry message.'); }
      });
      socket.addEventListener('error', () => onStatus('degraded'));
      socket.addEventListener('close', () => {
        if (stopped) return;
        onStatus('disconnected');
        const delay = Math.min(15000, 1000 * (2 ** Math.min(attempts, 4)));
        attempts += 1;
        retryTimer = window.setTimeout(connect, delay);
      });
    } catch (error) {
      onStatus('degraded', error instanceof Error ? error.message : 'Socket unavailable.');
      if (!stopped) retryTimer = window.setTimeout(connect, 5000);
    }
  };

  connect();
  const stop = () => {
    stopped = true;
    if (retryTimer !== null) window.clearTimeout(retryTimer);
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'Console teardown');
  };
  window.addEventListener('pagehide', stop, { once: true });
  return stop;
}
