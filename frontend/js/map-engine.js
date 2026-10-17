const DEFAULT_CENTER = [22.7467, 75.8947];
let map = null;
let overlayLayer = null;
let mapElement = null;
let fallbackElement = null;
let fallbackSvg = null;
let currentIncident = null;
let tileFailureCount = 0;
let usingFallback = false;

function makeIcon(type, label) {
  if (!window.L) return null;
  const className = {
    atm: 'map-pin map-pin-atm',
    csp: 'map-pin map-pin-csp',
    patrol: 'map-pin map-pin-patrol',
    origin: 'map-pin map-pin-origin',
    hotspot: 'map-pin map-pin-hotspot'
  }[type];
  const markup = type === 'patrol' ? `<span>${label}</span>` : label;
  return window.L.divIcon({ className: '', html: `<div class="${className}">${markup}</div>`, iconSize: type === 'hotspot' ? [25, 25] : [22, 22], iconAnchor: type === 'hotspot' ? [12, 12] : [11, 11] });
}

function showFallback() {
  usingFallback = true;
  if (mapElement) mapElement.style.display = 'none';
  if (fallbackElement) fallbackElement.hidden = false;
  if (currentIncident) drawSchematic(currentIncident);
}

function showLeaflet() {
  usingFallback = false;
  if (fallbackElement) fallbackElement.hidden = true;
  if (mapElement) mapElement.style.display = 'block';
  if (map) window.setTimeout(() => map.invalidateSize(), 50);
}

function svgNode(name, attributes = {}, text = '') {
  const element = document.createElementNS('http://www.w3.org/2000/svg', name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  if (text) element.textContent = text;
  return element;
}

function drawSchematic(incident) {
  if (!fallbackSvg || !incident) return;
  const group = document.createDocumentFragment();
  group.append(svgNode('rect', { x: 0, y: 0, width: 800, height: 520, fill: '#0b121d' }));
  // Geometric schematic intentionally avoids pretending to be a georeferenced street map.
  for (let i = 0; i < 11; i += 1) {
    const y = 22 + i * 48;
    group.append(svgNode('path', { d: `M -20 ${y} L 820 ${y + (i % 2 ? 13 : -8)}`, stroke: '#243244', 'stroke-width': i % 3 === 0 ? 8 : 4, fill: 'none' }));
  }
  for (let i = 0; i < 12; i += 1) {
    const x = 15 + i * 71;
    group.append(svgNode('path', { d: `M ${x} -20 L ${x + (i % 2 ? -16 : 18)} 540`, stroke: '#1d2b3b', 'stroke-width': i % 4 === 0 ? 7 : 3, fill: 'none' }));
  }
  for (let i = 0; i < 15; i += 1) {
    const x = 35 + (i * 53) % 735;
    const y = 34 + (i * 97) % 430;
    group.append(svgNode('rect', { x, y, width: 20 + (i % 3) * 10, height: 10 + (i % 2) * 13, fill: '#172636', stroke: '#304158', 'stroke-width': 1, opacity: '.7' }));
  }
  const hotspot = { x: 418, y: 263 };
  const source = { x: 226, y: 328 };
  const patrol = { x: 214, y: 144 };
  group.append(svgNode('circle', { cx: hotspot.x, cy: hotspot.y, r: 122, fill: '#10b981', 'fill-opacity': '.045', stroke: '#10b981', 'stroke-opacity': '.65', 'stroke-dasharray': '6 7', 'stroke-width': 1.5 }));
  group.append(svgNode('circle', { cx: hotspot.x, cy: hotspot.y, r: 51, fill: '#ef4444', 'fill-opacity': '.11', stroke: '#ef4444', 'stroke-opacity': '.9', 'stroke-width': 2 }));
  group.append(svgNode('path', { d: `M ${source.x} ${source.y} L ${hotspot.x} ${hotspot.y}`, stroke: '#f59e0b', 'stroke-width': 2, 'stroke-dasharray': '7 5', fill: 'none' }));
  group.append(svgNode('path', { d: `M ${patrol.x} ${patrol.y} L ${hotspot.x} ${hotspot.y}`, stroke: '#10b981', 'stroke-width': 2, 'stroke-dasharray': '4 5', fill: 'none' }));
  const markers = [
    { x: source.x, y: source.y, label: 'TX', color: '#94a3b8', title: 'LAST DIGITAL TX' },
    { x: 532, y: 227, label: 'A', color: '#38bdf8', title: 'BANK ATM' },
    { x: 492, y: 332, label: 'C', color: '#f59e0b', title: 'CSP / AEPS' },
    { x: 344, y: 209, label: 'A', color: '#38bdf8', title: 'BANK ATM' },
    { x: patrol.x, y: patrol.y, label: 'P', color: '#10b981', title: incident.patrol?.unitId || 'PCR PATROL' },
    { x: hotspot.x, y: hotspot.y, label: '!', color: '#ef4444', title: 'FORECAST HOTSPOT' }
  ];
  markers.forEach((marker) => {
    group.append(svgNode('rect', { x: marker.x - 10, y: marker.y - 10, width: 20, height: 20, fill: '#0a0d14', stroke: marker.color, 'stroke-width': 1.5 }));
    group.append(svgNode('text', { x: marker.x, y: marker.y + 4, 'text-anchor': 'middle', fill: marker.color, 'font-size': 11, 'font-family': 'monospace', 'font-weight': 700 }, marker.label));
    group.append(svgNode('text', { x: marker.x + 13, y: marker.y - 12, fill: '#cad5e2', 'font-size': 9, 'font-family': 'monospace' }, marker.title));
  });
  group.append(svgNode('text', { x: 18, y: 25, fill: '#8ea1b8', 'font-size': 10, 'font-family': 'monospace', 'letter-spacing': 1.5 }, `${incident.city.toUpperCase()} / ${incident.area.toUpperCase()} — SCHEMATIC`));
  group.append(svgNode('text', { x: hotspot.x, y: hotspot.y + 74, 'text-anchor': 'middle', fill: '#fca5a5', 'font-size': 9, 'font-family': 'monospace' }, `RADIUS ${incident.predictedExit.radiusMeters} M`));
  fallbackSvg.replaceChildren(group);
}

export function initMap() {
  mapElement = document.getElementById('tactical-map');
  fallbackElement = document.getElementById('map-fallback');
  fallbackSvg = document.getElementById('fallback-svg');
  if (!window.L || !mapElement) {
    showFallback();
    return false;
  }
  try {
    map = window.L.map(mapElement, { zoomControl: true, scrollWheelZoom: true, preferCanvas: true, zoomSnap: 0.5 }).setView(DEFAULT_CENTER, 14.5);
    overlayLayer = window.L.layerGroup().addTo(map);
    const tiles = window.L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd', maxZoom: 19, attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
    });
    tiles.on('tileerror', () => {
      tileFailureCount += 1;
      if (tileFailureCount >= 5) showFallback();
    });
    tiles.on('load', () => {
      if (tileFailureCount < 5) showLeaflet();
    });
    tiles.addTo(map);
    window.setTimeout(() => map?.invalidateSize(), 100);
    return true;
  } catch (error) {
    console.warn('Leaflet initialization failed; using schematic map.', error);
    showFallback();
    return false;
  }
}

function popupContent(title, detail) {
  const wrapper = document.createElement('div');
  const strong = document.createElement('b');
  strong.textContent = title;
  const small = document.createElement('small');
  small.textContent = detail;
  wrapper.append(strong, small);
  return wrapper;
}

export function renderIncidentOnMap(incident, { fit = false, remainingSeconds = null } = {}) {
  currentIncident = incident;
  if (!incident) return;
  if (!map || !overlayLayer) {
    showFallback();
    drawSchematic(incident);
    return;
  }
  if (usingFallback) {
    drawSchematic(incident);
    return;
  }

  overlayLayer.clearLayers();
  const L = window.L;
  const exit = incident.predictedExit;
  const source = incident.source;
  const patrol = incident.patrol;
  const exitPoint = [exit.lat, exit.lon];
  const sourcePoint = [source.lat, source.lon];
  const patrolPoint = [patrol.lat, patrol.lon];
  const liveEta = Number.isFinite(patrol.etaDeadlineMs) ? Math.max(0, (patrol.etaDeadlineMs - Date.now()) / 60000) : patrol.etaMinutes;

  L.circle(exitPoint, { radius: 650, color: '#10b981', weight: 1, opacity: 0.7, dashArray: '5 7', fillColor: '#10b981', fillOpacity: 0.025 }).bindTooltip('5–10 MIN EST. MOVEMENT PERIMETER · APPROXIMATION').addTo(overlayLayer);
  L.circle(exitPoint, { radius: Number(exit.radiusMeters) || 280, color: '#ef4444', weight: 2, opacity: 0.9, fillColor: '#ef4444', fillOpacity: 0.12 }).bindTooltip(`Forecast hotspot · ${exit.radiusMeters} m radius · ${incident.confidence}% model confidence`).addTo(overlayLayer);
  L.polyline([sourcePoint, exitPoint], { color: '#f59e0b', weight: 2, opacity: 0.9, dashArray: '6 6' }).bindTooltip('Source-to-exit hypothesis — inferred path, not a confirmed route').addTo(overlayLayer);
  L.polyline([patrolPoint, exitPoint], { color: '#10b981', weight: 2, opacity: 0.9, dashArray: '4 5' }).bindTooltip(`${patrol.unitId} · ${patrol.state || 'STANDBY'} · ETA ${Math.max(0, liveEta).toFixed(1)} min`).addTo(overlayLayer);

  L.marker(sourcePoint, { icon: makeIcon('origin', 'TX'), keyboard: true, title: source.label }).bindPopup(popupContent('LAST DIGITAL TRANSACTION', source.label)).addTo(overlayLayer);
  L.marker(exitPoint, { icon: makeIcon('hotspot', '!'), keyboard: true, title: `Forecast exit: ${exit.name}` }).bindPopup(popupContent('PREDICTED CASH-OUT ZONE', `${exit.name} · ${exit.radiusMeters} m estimate · ${incident.confidence}% confidence`)).addTo(overlayLayer);
  L.marker(patrolPoint, { icon: makeIcon('patrol', 'P'), keyboard: true, title: `${patrol.unitId} patrol unit` }).bindPopup(popupContent(patrol.unitId, `${patrol.state || 'STANDBY'} · ETA ${Math.max(0, liveEta).toFixed(1)} min`)).addTo(overlayLayer);

  (incident.cashpoints || []).forEach((cashpoint) => {
    const isCsp = String(cashpoint.type).toUpperCase().includes('CSP');
    L.marker([cashpoint.lat, cashpoint.lon], { icon: makeIcon(isCsp ? 'csp' : 'atm', isCsp ? 'C' : 'A'), keyboard: true, title: cashpoint.name })
      .bindPopup(popupContent(cashpoint.type, cashpoint.name)).addTo(overlayLayer);
  });

  if (fit) {
    const points = [exitPoint, sourcePoint, patrolPoint, ...(incident.cashpoints || []).map((cashpoint) => [cashpoint.lat, cashpoint.lon])];
    map.fitBounds(L.latLngBounds(points).pad(0.24), { maxZoom: 16, animate: true, duration: 0.5 });
  }
  if (remainingSeconds !== null) {
    const statusNode = document.getElementById('map-countdown-overlay');
    if (statusNode) statusNode.textContent = remainingSeconds > 0 ? `T− ${Math.floor(remainingSeconds / 60).toString().padStart(2, '0')}:${Math.floor(remainingSeconds % 60).toString().padStart(2, '0')}` : 'T− 00:00';
  }
}

export function recenterMap() {
  if (map && currentIncident && !usingFallback) {
    renderIncidentOnMap(currentIncident, { fit: true });
  } else if (currentIncident) {
    drawSchematic(currentIncident);
  }
}

export function getMapMode() {
  return map && !usingFallback ? 'leaflet' : 'schematic';
}
