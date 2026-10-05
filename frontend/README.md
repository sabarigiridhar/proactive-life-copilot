# Life Copilot web client

This directory contains the typed Next.js frontend for Life Copilot. Streamlit remains
available as the admin/debug client until Phase 5 reaches feature parity.

## Requirements

- Node.js 20.9 or newer
- Python environment with the root `requirements.txt` installed
- FastAPI running on port 8000 for local development

## First-time local setup

```powershell
cd B:\My_Tracker
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

cd B:\My_Tracker\frontend
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm.cmd install
npm.cmd run generate:api
```

## Run the application

Start FastAPI in one PowerShell window:

```powershell
cd B:\My_Tracker
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Start Next.js in a second PowerShell window:

```powershell
cd B:\My_Tracker\frontend
npm.cmd run dev
```

Open `http://localhost:3000`. FastAPI documentation is available at
`http://127.0.0.1:8000/docs`. The default `.env.example` points to
`http://127.0.0.1:8000`; change `NEXT_PUBLIC_LIFE_COPILOT_API_URL` per environment.
Never place provider keys in a `NEXT_PUBLIC_*` variable because those values are sent
to the browser.

## Verification

```powershell
npm.cmd run check
npm.cmd run build
npm.cmd audit
```

## API types

`npm.cmd run generate:api` exports the current FastAPI OpenAPI document to `openapi.json`
and regenerates `src/lib/api/schema.d.ts`. Run it whenever a backend route or model
changes. The HTTP wrapper in `src/lib/api/client.ts` uses those generated path and
schema types through `openapi-fetch`.

## Foundation decisions

See `docs/decisions/0001-ui-and-chart-libraries.md` for the React Aria, Recharts,
Lucide, CSS, and Biome decisions.
