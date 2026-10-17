# CYBER-TRAC Tactical Situational Awareness Console

A dependency-light, no-build vanilla JavaScript frontend prototype for the IBM Z Datathon 2026. The supplied records, predictive estimates, map facility labels, telemetry values, patrol activity, dispatch events and switch-hold acknowledgements are **synthetic demonstration content**. This project does not connect to I4C, NCRP, 1930, banks, NPCI, police dispatch, or any live surveillance system.

## Run locally

Modern browsers restrict JavaScript ES modules and `fetch()` from `file://` URLs. Because this app intentionally uses ES modules and loads `data/mock-incidents.json` over HTTP, use a local server instead of double-clicking `index.html`:

### Windows
Double-click `start-server.bat`. It opens `http://localhost:8000` and starts Python's built-in HTTP server in the terminal. Keep that terminal open while using the app.

### macOS / Linux / any machine with Python 3
From this directory, run:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000> in a modern browser. No package installation, build step, or Node runtime is needed.

The dashboard requests Leaflet from a public CDN and CartoDB Dark Matter map tiles. Internet access is needed for the interactive street map; if the Leaflet library is unavailable or repeated tile requests fail, a clearly labeled schematic map fallback is shown. Core incident triage, timers, transaction graph, and local demo actions do not require the map tile service.

## Directory structure

```text
cyber-tactical-dashboard/
├── index.html
├── README.md
├── start-server.bat
├── css/
│   ├── design-tokens.css
│   ├── layout.css
│   └── components.css
├── js/
│   ├── app.js
│   ├── api-client.js
│   ├── map-engine.js
│   ├── incident-feed.js
│   ├── mule-graph.js
│   └── simulation-engine.js
└── data/
    └── mock-incidents.json
```

## Included interactions

- Filter incidents by all, critical countdown, high value, and linked mule ring; search by incident ID, city, modus, area or forecast site.
- Select an incident to synchronize the map, graph, forecast details and countdowns.
- Visualize synthetic ATM/CSP markers, forecast radius, approximate 5–10 minute movement perimeter, last digital transaction and PCR route vector.
- Dispatch a simulated patrol after confirmation; unit state and estimated arrival countdown update locally.
- Simulate a switch-hold acknowledgement locally; no external bank or switch message is transmitted.
- Generate and print a field-advisory preview.
- Run a scripted scenario that adds a new synthetic high-value complaint, steps through graph/hotspot statuses and simulates patrol assignment.
- See live IST/UTC clocks, urgency countdowns, local event log, responsive layouts and a reduced-motion mode.

## Optional read-only backend integration

In `index.html`, configure `window.CYBER_TRAC_CONFIG`:

```html
<script>
  window.CYBER_TRAC_CONFIG = Object.freeze({
    apiBaseUrl: "https://your-authorized-api.example",
    incidentsPath: "/api/incidents",
    webSocketUrl: "wss://your-authorized-api.example/telemetry"
  });
</script>
```

The REST endpoint should return either an array of incident objects or `{ "records": [...] }` / `{ "incidents": [...] }` that conform to the schema in `data/mock-incidents.json`. WebSocket read-only messages supported by `js/api-client.js` are:

```json
{ "type": "incident.upsert", "incident": { "...": "record matching mock schema" } }
{ "type": "incident.remove", "id": "NCRP-..." }
{ "type": "telemetry", "latencyMs": 3.4 }
```

The frontend expects the backend to enforce authentication, authorization, audit trails, input validation, rate limits and any required approval process. Do not place API secrets or long-lived credentials in this static frontend. Use HTTPS/WSS outside localhost. The provided action controls are deliberately simulation-only; a real dispatch, account freeze or bank-switch control requires a separately designed, authenticated, audited backend action contract and explicit operational authorization.

## Data contract

Each incident includes an identifier, city/area, fraud modality, amount, countdown duration, confidence, synthetic source coordinates, predicted exit details and radius, patrol unit coordinates/ETA, nearby cash-point markers, and an illustrative transaction path. All bank/site identifiers and account tokens are demo labels, not validated identifiers.

## Notes for a judging demo

- The scripted scenario is local to the page and can be replayed.
- Map predictions are model-style visual estimates; the displayed perimeter is a schematic radius rather than a road-network routing isochrone.
- The `3.4 ms` latency in default mode is sample telemetry. If a configured telemetry socket sends `latencyMs`, the header is updated from that read-only feed.
- Do not use synthetic values, locations or advisories for real operational decisions.
