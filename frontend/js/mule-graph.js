const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(name, attrs = {}, text = '') {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
  if (text !== '') node.textContent = text;
  return node;
}

function truncate(text, max = 17) {
  const value = String(text || 'UNKNOWN');
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

export function renderMuleGraph(incident) {
  const svg = document.getElementById('mule-graph');
  if (!svg || !incident) return;
  const nodes = Array.isArray(incident.transactionPath) ? incident.transactionPath : [];
  const width = 460;
  const height = 205;
  svg.replaceChildren();
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.append(svgEl('title', {}, `Synthetic transaction path for ${incident.id}`));
  svg.append(svgEl('desc', {}, 'Illustrative directed flow from victim account to first-hop mule, second-hop mule, and forecast cash-out exit.'));
  const defs = svgEl('defs');
  const marker = svgEl('marker', { id: 'graph-arrow', markerWidth: 7, markerHeight: 7, refX: 5, refY: 3, orient: 'auto', markerUnits: 'strokeWidth' });
  marker.append(svgEl('path', { d: 'M0,0 L6,3 L0,6 z', fill: '#64748b' }));
  defs.append(marker);
  svg.append(defs);
  svg.append(svgEl('rect', { x: 0, y: 0, width, height, fill: '#0c111b' }));
  for (let y = 10; y < height; y += 20) svg.append(svgEl('path', { d: `M0 ${y} H${width}`, stroke: '#172130', 'stroke-width': 1 }));

  const fallbackNodes = [
    { label: 'VICTIM', bank: 'Origin account', amountINR: incident.amountINR },
    { label: 'TIER-1 MULE', bank: 'Bank hop 01', amountINR: incident.amountINR * 0.98 },
    { label: 'TIER-2 MULE', bank: 'Bank hop 02', amountINR: incident.amountINR * 0.85 },
    { label: 'FLAGGED EXIT', bank: incident.predictedExit?.name || 'Predicted exit', amountINR: incident.amountINR * 0.5 }
  ];
  const safeNodes = nodes.length ? nodes.slice(0, 4) : fallbackNodes;
  while (safeNodes.length < 4) safeNodes.push(fallbackNodes[safeNodes.length]);
  const nodeW = 94;
  const nodeH = 72;
  const xs = [7, 122, 237, 352];
  const y = 53;
  const colors = [
    { stroke: '#64748b', fill: '#1e293b', text: '#d5dce6', caption: '#94a3b8' },
    { stroke: '#c18b2a', fill: '#302616', text: '#ffe0a3', caption: '#c7a66c' },
    { stroke: '#c18b2a', fill: '#302616', text: '#ffe0a3', caption: '#c7a66c' },
    { stroke: '#ef4444', fill: '#3a1d25', text: '#ffb4b4', caption: '#ef8888' }
  ];

  for (let index = 0; index < 3; index += 1) {
    const fromX = xs[index] + nodeW;
    const toX = xs[index + 1] - 5;
    const amount = Number(safeNodes[index + 1]?.amountINR);
    const previous = Number(safeNodes[index]?.amountINR);
    const label = Number.isFinite(amount) && Number.isFinite(previous) && previous > 0 ? `${Math.max(0, Math.round((previous - amount) / previous * 100))}% delta` : 'trace link';
    svg.append(svgEl('path', { d: `M${fromX} ${y + 34} H${toX}`, stroke: '#64748b', 'stroke-width': 1.5, 'marker-end': 'url(#graph-arrow)' }));
    svg.append(svgEl('text', { x: (fromX + toX) / 2, y: y - 7, fill: '#77869c', 'text-anchor': 'middle', 'font-size': 7, 'font-family': 'monospace' }, label));
  }

  safeNodes.forEach((node, index) => {
    const x = xs[index];
    const color = colors[index];
    svg.append(svgEl('rect', { x, y, width: nodeW, height: nodeH, fill: color.fill, stroke: color.stroke, 'stroke-width': index === 3 ? 1.6 : 1 }));
    svg.append(svgEl('rect', { x, y, width: 3, height: nodeH, fill: color.stroke }));
    svg.append(svgEl('text', { x: x + 9, y: y + 14, fill: color.caption, 'font-size': 7, 'font-family': 'monospace', 'font-weight': 700 }, ['SOURCE', 'LAYER 01', 'LAYER 02', 'FORECAST'][index]));
    const label = index === 3 ? 'FLAGGED EXIT' : truncate(node.label || `NODE ${index + 1}`, 14);
    svg.append(svgEl('text', { x: x + 9, y: y + 30, fill: color.text, 'font-size': 9, 'font-family': 'monospace', 'font-weight': 700 }, label));
    svg.append(svgEl('text', { x: x + 9, y: y + 44, fill: '#b2bece', 'font-size': 8, 'font-family': 'system-ui, sans-serif' }, truncate(node.bank, 16)));
    const value = Number(node.amountINR);
    const amountLabel = Number.isFinite(value) ? `₹${new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(value)}` : 'AMOUNT N/A';
    svg.append(svgEl('text', { x: x + 9, y: y + 60, fill: color.caption, 'font-size': 9, 'font-family': 'monospace', 'font-weight': 600 }, amountLabel));
  });
  svg.append(svgEl('text', { x: 8, y: 151, fill: '#7c8ba0', 'font-size': 8, 'font-family': 'monospace' }, 'DIRECTED FLOW / DEMO GRAPH'));
  svg.append(svgEl('text', { x: 8, y: 166, fill: '#7c8ba0', 'font-size': 8, 'font-family': 'monospace' }, 'DAG PATH IS ILLUSTRATIVE — NOT BANK-CONFIRMED'));
  svg.append(svgEl('text', { x: 8, y: 188, fill: '#42516a', 'font-size': 7, 'font-family': 'monospace' }, `CASE ${incident.id} · ${safeNodes.length} NODES / ${safeNodes.length - 1} EDGES`));
  const nodeCount = document.getElementById('graph-node-count');
  if (nodeCount) nodeCount.textContent = `${safeNodes.length} NODES / ${safeNodes.length - 1} EDGES`;
}
