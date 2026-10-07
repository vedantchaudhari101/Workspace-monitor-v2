# Workspace Monitor — web app

React 19 + Vite. See the root README for setup.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api and the WebSocket to :8000
npm run build    # production build in dist/ (served by the API when FRONTEND_DIST is set)
npm run lint
```

Structure:

* `src/lib/live/store.js` — one shared WebSocket; components subscribe to the seat or camera they render.
* `src/lib/workspace.jsx` — current building, camera, teams and the demo-data switch.
* `src/components/shell` — navigation rail, ambient floor-grid background, pointer companion.
* `src/components/data` — seat map (camera-pixel coordinates), seat grid, charts, heatmap.
* `src/features/analysis` — upload console with real pipeline stages, session summary.
* `src/styles/tokens.css` — colours, type and spacing. Red/green are reserved for occupancy.
