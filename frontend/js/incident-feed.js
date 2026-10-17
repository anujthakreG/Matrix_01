const moneyFormatter = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });

export function formatMoney(amount) {
  return moneyFormatter.format(Number(amount) || 0).replace(/\u00a0/g, ' ');
}

export function getRemainingSeconds(incident, now = Date.now()) {
  if (Number.isFinite(incident.deadlineMs)) return Math.max(0, Math.ceil((incident.deadlineMs - now) / 1000));
  return Math.max(0, Number(incident.remainingSeconds) || 0);
}

export function formatCountdown(totalSeconds) {
  const safe = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  return hours > 0
    ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function severityFor(incident, remaining) {
  if (remaining <= 0) return 'expired';
  if (remaining <= 900) return 'critical';
  if (incident.amountINR >= 200000 || incident.confidence >= 85) return 'high';
  return 'monitor';
}

function textElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function makeIncidentCard(incident, selectedId, onSelect, now) {
  const remaining = getRemainingSeconds(incident, now);
  const severity = severityFor(incident, remaining);
  const card = document.createElement('button');
  card.type = 'button';
  card.className = `incident-card severity-${severity}${incident.id === selectedId ? ' is-selected' : ''}`;
  card.dataset.id = incident.id;
  card.setAttribute('aria-pressed', String(incident.id === selectedId));
  card.setAttribute('aria-label', `${incident.id}, ${incident.fraudType}, ${formatMoney(incident.amountINR)}, ${remaining > 0 ? `${formatCountdown(remaining)} remaining` : 'window expired'}`);
  card.addEventListener('click', () => onSelect(incident.id));

  const top = document.createElement('div');
  top.className = 'incident-topline';
  const idRow = document.createElement('div');
  idRow.className = 'incident-id-row';
  idRow.append(textElement('span', 'incident-id', `#${incident.id}`));
  const labels = {
    critical: ['CRITICAL', 'severity-badge badge-critical'],
    high: ['HIGH', 'severity-badge badge-high'],
    monitor: ['MONITOR', 'severity-badge badge-monitor'],
    expired: ['EXPIRED', 'severity-badge badge-expired']
  };
  idRow.append(textElement('span', labels[severity][1], labels[severity][0]));
  top.append(idRow, textElement('span', 'incident-time', incident.complaintReceived || 'DEMO FEED'));

  const modus = textElement('div', 'incident-modus', incident.fraudType);
  const city = textElement('div', 'incident-city', `${incident.area} · ${incident.city}, ${incident.state}`);
  const amountRow = document.createElement('div');
  amountRow.className = 'incident-amount-row';
  const amountWrap = document.createElement('div');
  amountWrap.append(textElement('div', 'incident-amount', formatMoney(incident.amountINR)), textElement('div', 'incident-amount-label', 'SUSPECTED EXPOSURE'));
  const confidence = textElement('span', 'incident-confidence', `${Math.round(incident.confidence)}% SPATIAL`);
  amountRow.append(amountWrap, confidence);

  const timerRow = document.createElement('div');
  timerRow.className = 'incident-timer-row';
  timerRow.append(textElement('span', 'incident-timer-label', 'GOLDEN WINDOW'));
  const timer = textElement('time', `incident-timer${remaining <= 900 && remaining > 0 ? ' timer-critical' : ''}${remaining <= 0 ? ' timer-expired' : ''}`, remaining > 0 ? `T− ${formatCountdown(remaining)}` : 'WINDOW EXPIRED');
  timer.dataset.timer = 'true';
  timer.setAttribute('datetime', `PT${remaining}S`);
  timerRow.append(timer);

  const track = document.createElement('div');
  track.className = 'countdown-track';
  const fill = document.createElement('span');
  fill.className = `countdown-fill${remaining <= 900 && remaining > 0 ? ' fill-critical' : ''}${remaining <= 0 ? ' fill-expired' : ''}`;
  fill.dataset.progress = 'true';
  const initial = Math.max(1, Number(incident.initialWindowSeconds) || Number(incident.remainingSeconds) || 1800);
  fill.style.width = `${Math.max(0, Math.min(100, remaining / initial * 100))}%`;
  track.append(fill);

  const bottom = document.createElement('div');
  bottom.className = 'incident-bottomline';
  const ring = textElement('span', 'incident-ring', incident.muleRingLinked ? '● MULE RING LINKED' : '○ RING UNCONFIRMED');
  const location = textElement('span', 'incident-location-chip', incident.predictedExit?.name || 'EXIT LOCATION PENDING');
  bottom.append(ring, location);

  card.append(top, modus, city, amountRow, timerRow, track, bottom);
  return card;
}

export function renderIncidentFeed({ container, incidents, selectedId, filter, search, onSelect }) {
  const now = Date.now();
  const normalizedSearch = String(search || '').trim().toLowerCase();
  const filtered = incidents.filter((incident) => {
    const remaining = getRemainingSeconds(incident, now);
    if (filter === 'critical' && !(remaining > 0 && remaining <= 900)) return false;
    if (filter === 'value' && incident.amountINR <= 200000) return false;
    if (filter === 'mule' && !incident.muleRingLinked) return false;
    if (normalizedSearch) {
      const haystack = [incident.id, incident.city, incident.state, incident.area, incident.fraudType, incident.predictedExit?.name]
        .filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(normalizedSearch)) return false;
    }
    return true;
  });

  const fragment = document.createDocumentFragment();
  if (filtered.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.append(textElement('strong', '', 'NO MATCHING RECORDS'), textElement('span', '', 'Change the filter or search term.'));
    fragment.append(empty);
  } else {
    filtered.forEach((incident) => fragment.append(makeIncidentCard(incident, selectedId, onSelect, now)));
  }
  container.replaceChildren(fragment);
  return filtered.length;
}

export function updateLiveCountdowns(incidents) {
  const now = Date.now();
  document.querySelectorAll('.incident-card[data-id]').forEach((card) => {
    const incident = incidents.find((item) => item.id === card.dataset.id);
    if (!incident) return;
    const remaining = getRemainingSeconds(incident, now);
    const timer = card.querySelector('[data-timer]');
    const fill = card.querySelector('[data-progress]');
    if (timer) {
      timer.textContent = remaining > 0 ? `T− ${formatCountdown(remaining)}` : 'WINDOW EXPIRED';
      timer.classList.toggle('timer-critical', remaining > 0 && remaining <= 900);
      timer.classList.toggle('timer-expired', remaining <= 0);
      timer.dateTime = `PT${remaining}S`;
    }
    if (fill) {
      const initial = Math.max(1, Number(incident.initialWindowSeconds) || Number(incident.remainingSeconds) || 1800);
      fill.style.width = `${Math.max(0, Math.min(100, remaining / initial * 100))}%`;
      fill.classList.toggle('fill-critical', remaining > 0 && remaining <= 900);
      fill.classList.toggle('fill-expired', remaining <= 0);
    }
    const severity = severityFor(incident, remaining);
    card.classList.remove('severity-critical', 'severity-high', 'severity-monitor', 'severity-expired');
    card.classList.add(`severity-${severity}`);
    const badge = card.querySelector('.severity-badge');
    if (badge) {
      const display = { critical: ['CRITICAL', 'badge-critical'], high: ['HIGH', 'badge-high'], monitor: ['MONITOR', 'badge-monitor'], expired: ['EXPIRED', 'badge-expired'] }[severity];
      badge.textContent = display[0];
      badge.className = `severity-badge ${display[1]}`;
    }
  });
}
