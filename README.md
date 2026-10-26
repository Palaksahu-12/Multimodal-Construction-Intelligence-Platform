# Multimodal Construction Intelligence Platform

React/Vite frontend and FastAPI backend for construction image review, conceptual planning, indicative property calculations, and construction guidance. Outputs are decision-support only and are not certified engineering, safety, appraisal, legal, or financial advice.

## Features and status

- Site safety image review and crack observation use Google Gemini multimodal analysis.
- Construction planning returns sequential conceptual phases with dependencies, internally reconciled durations and costs, broad material quantities, assumptions, and key risks. Its defaults are illustrative planning factors, not current market rates or a bill of quantities.
- Property valuation is calculated only from a user-supplied local reference rate. Without one, the API returns `NEEDS_LOCAL_REFERENCE_RATE`, not a fabricated value.
- The construction assistant and daily site assistant use Gemini. Daily summaries are grounded in the facts the user submits.
- The weather advisory does not retrieve live weather. It reports `INSUFFICIENT INFORMATION` until the user supplies conditions, and labels those conditions as unverified.
- Document generation, live weather lookup, live material/property pricing, and architectural image generation are not connected.

## Requirements baseline

Functional requirements implemented:

- Analyze construction images for visible safety concerns and apparent cracks, with evidence, uncertainty, limitations, and practical next steps.
- Provide a conceptual construction plan with material allowances, phase durations, cost assumptions, and exclusions.
- Calculate an INR property range only when a user-supplied local reference rate is available; optionally calculate rent and gross yield from user-supplied inputs.
- Answer construction questions, organize user-reported daily site information, and provide cautious weather advice based only on user-entered observations.
- Validate API input and model output, provide machine-readable responses, and display request loading, success, and error states in the existing React app.

Non-functional requirements:

- Keep Gemini credentials on the backend and avoid logging or returning credentials.
- Use explicit Pydantic request/response contracts, sanitized provider errors, and bounded retry behavior.
- Preserve image size/type/integrity checks, useful HTTP errors, and configurable CORS origins.
- Mark AI analysis and all non-market-derived calculations as decision support with stated assumptions and limitations.

## Requirements and setup

Prerequisites:

- Python 3.10 or newer
- Node.js 22 and npm 10 (tested in this workspace; use a Node release supported by the pinned Vite version)
- A Google Gemini API key for the image-analysis, chat, daily-site, and weather-advisory AI workflows

Create and install the backend environment in PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Put the key in `backend/.env` as `GEMINI_API_KEY=...`. Do not commit or share that file. `CORS_ORIGINS` is optional and defaults to the two local Vite origins; the two configured Vercel frontend origins are always included. Additional trusted origins can be supplied as a comma-separated allowlist. CORS credentials remain enabled, with no wildcard origin.

Start FastAPI:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

The UI defaults to `http://127.0.0.1:8000`. Set `VITE_API_BASE_URL` in `frontend/.env.local` to change the API origin. Vite environment values are public; never put server credentials there.

## API

Interactive Swagger documentation is available at `http://127.0.0.1:8000/docs`.

| Method and path | Request | Behavior |
| --- | --- | --- |
| `GET /health` | none | Backend liveness |
| `POST /api/site-safety/analyze` | multipart `image`, optional `context` | Validates JPEG/PNG/WEBP and up to 10 MB; returns `analysis` with summary, risk, hazards, PPE concerns, and limitations |
| `POST /api/crack-analysis/analyze` | multipart `image`, optional `context` | Returns visible crack characteristics, indicative severity, possible causes, next steps, and limitations |
| `POST /api/project-plan` | JSON `project_type` (Residential, Commercial, Renovation), `built_up_area_sqm`, `floors`, optional `budget_inr`, `target_timeline_days`, `location` | Returns indicative cost breakdown, sequential dependencies, summed durations, risks, and broad material allowances |
| `POST /api/property-valuation` | JSON property details including `area_sqm` (legacy `built_up_area_sqm` is accepted), optional user-supplied `reference_price_per_sqm_inr`, rent and investment inputs | Returns a clearly indicative INR calculation or requests a local reference rate |
| `POST /api/chat` | JSON `message`, optional recent `history` | Returns a concise answer and caveats |
| `POST /api/daily-site-assistant` | JSON `site_update`, optional activities, workforce, resources, and constraints | Returns summary, reported progress, pending tasks, risks, next actions, and limitations |
| `POST /api/weather-advisory` | JSON `activity` and optional user-provided weather observations | Returns GO/NO-GO/INSUFFICIENT INFORMATION; does not fetch or claim live conditions |

JSON validation failures use HTTP 422. Image type/content failures use HTTP 400; image payloads above 10 MB use HTTP 413. AI failures are returned as sanitized errors, distinguishing configuration/access, quota/rate limits, timeouts, and upstream outages. Gemini is configured server-side with a 60-second request timeout and bounded exponential retry/backoff with jitter for transient connection and service failures. AI responses with missing required fields or inconsistent project totals are rejected instead of being filled with success-shaped defaults.

## Tests and build

From the backend directory:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

The tests mock Gemini and cover image validation and forwarding, contracts, estimates, blank input, weather without observations, malformed model output, transient timeouts, quota failures, and upstream errors. They do not require a successful external Gemini call.

From the frontend directory:

```powershell
npm run lint
npm run build
```

## Deployment notes

- Keep `GEMINI_API_KEY` in the deployment platform's backend secret/environment-variable store.
- Run Uvicorn behind a TLS-terminating reverse proxy or the hosting platform's HTTPS ingress; bind to the platform-provided host/port as required.
- The two project Vercel origins are explicitly allowed by the backend; add any other trusted frontend origins to `CORS_ORIGINS`. Do not use a wildcard with credentials.
- Set the frontend's `VITE_API_BASE_URL` at build time to the deployed HTTPS API origin.
- Deploy the frontend's Vite production build (`npm run build`, output in `frontend/dist`) to a static host and deploy the FastAPI backend separately.
- Planning and valuation outputs contain broad illustrative assumptions; integrate verified local pricing data and professional review before operational use. Live weather and architectural image-generation integrations are not configured.

## Manual verification

1. Start both applications and open `http://localhost:5173`; test the backend connection indicator.
2. In Site Analysis, submit a valid site image, an unsupported file, a corrupt image, and an image above 10 MB. Verify errors remain visible and no AI result is fabricated when Gemini is unavailable.
3. In Crack Detection, upload a building image and check the limitations and qualified-review guidance.
4. Generate a conceptual plan with an explicit budget, then without one; compare the assumptions and phase breakdown.
5. Request a property estimate without a local reference rate (no numeric valuation should appear), then with a rate supplied by you.
6. Test a chat message and a daily report; verify outputs reflect submitted context only.
7. Request a weather advisory without observations (it must be insufficient information), then with user-entered conditions (the response must identify them as unverified).
