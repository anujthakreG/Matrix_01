let scenarioSequence = 0;

export function createScenarioIncident() {
  scenarioSequence += 1;
  const suffix = String(scenarioSequence).padStart(2, '0');
  const now = Date.now();
  const remainingSeconds = 14 * 60 + 30;
  return {
    id: `NCRP-DEMO-${suffix}`,
    city: 'Indore',
    state: 'Madhya Pradesh',
    area: 'Vijay Nagar / Scheme 54',
    fraudType: 'High-value Phishing + APK Sideload',
    amountINR: 560000,
    remainingSeconds,
    initialWindowSeconds: remainingSeconds,
    deadlineMs: now + remainingSeconds * 1000,
    confidence: 91,
    muleRingLinked: true,
    complaintReceived: 'LIVE DEMO INTAKE',
    status: 'DEMO INTAKE RECEIVED',
    isSimulation: true,
    demoPhase: 'INTAKE RECEIVED',
    source: { lat: 22.7545, lon: 75.8879, label: 'Synthetic last digital transaction' },
    predictedExit: {
      name: 'Demo ATM IN-4402',
      type: 'BANK ATM',
      bank: 'Demo bank switch route',
      address: 'Scheme 54 approach road, Vijay Nagar, Indore',
      landmark: 'Near Scheme 54 commercial block (synthetic label)',
      lat: 22.7482,
      lon: 75.8961,
      radiusMeters: 270,
      etaMinutes: 4.6,
      suspectToken: 'CARD •••• DEMO-4402',
      facilityId: 'DEMO-ATM-IN4402'
    },
    patrol: { unitId: 'PCR-06', lat: 22.7605, lon: 75.8817, etaMinutes: 4.6, state: 'STANDBY' },
    cashpoints: [
      { id: 'DEMO-CP-01', type: 'ATM', name: 'Demo ATM north', lat: 22.7502, lon: 75.8903 },
      { id: 'DEMO-CP-02', type: 'CSP', name: 'Demo CSP / AEPS point', lat: 22.7462, lon: 75.9002 },
      { id: 'DEMO-CP-03', type: 'ATM', name: 'Demo ATM east', lat: 22.7514, lon: 75.9011 }
    ],
    transactionPath: [
      { id: 'demo-v1', label: 'VICTIM', bank: 'SBI', role: 'Synthetic victim account', amountINR: 560000 },
      { id: 'demo-m1', label: 'TIER-1 MULE', bank: 'HDFC Bank', role: 'Synthetic first-hop mule', amountINR: 552000 },
      { id: 'demo-m2', label: 'TIER-2 MULE', bank: 'Airtel Payments', role: 'Synthetic layering account', amountINR: 489000 },
      { id: 'demo-x1', label: 'FLAGGED EXIT', bank: 'Demo ATM IN-4402', role: 'Synthetic forecast exit', amountINR: 225000 }
    ],
    analystNote: 'Scripted judging-demo scenario. All entities, amounts, paths and response events are synthetic.'
  };
}

export async function runScenarioSteps({ incident, selectIncident, dispatchPatrol, addLog, toast }) {
  // The explicit demo button authorizes this scripted sequence; every side effect is local UI state only.
  const phases = [
    { wait: 150, phase: 'INTAKE RECEIVED', status: 'DEMO INTAKE RECEIVED', log: 'SIMULATION: high-value complaint ingested; countdown started.' },
    { wait: 850, phase: 'MULE TRACE RESOLVED', status: 'GRAPH CORRELATED', log: 'SIMULATION: four-node transaction path resolved across three synthetic hops.' },
    { wait: 900, phase: 'HOTSPOT FORECASTED', status: 'FORECAST GENERATED', log: 'SIMULATION: 270 m candidate zone calculated around the Indore demo cluster.' },
    { wait: 1100, phase: 'PCR ROUTE ASSIGNED', status: 'PATROL EN ROUTE', log: 'SIMULATION: nearest demo patrol route assigned; ETA countdown started.' }
  ];
  for (const step of phases) {
    await new Promise((resolve) => window.setTimeout(resolve, step.wait));
    incident.demoPhase = step.phase;
    incident.status = step.status;
    if (step.phase === 'PCR ROUTE ASSIGNED') dispatchPatrol(incident, { silent: true, source: 'scripted scenario' });
    addLog(step.log, step.phase === 'PCR ROUTE ASSIGNED' ? 'dispatch' : 'demo');
    selectIncident(incident.id, { fit: true, scenarioStep: true });
    toast(step.phase, step.phase === 'PCR ROUTE ASSIGNED' ? 'success' : 'info');
  }
}
