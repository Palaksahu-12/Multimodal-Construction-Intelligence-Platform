# ConstructAI frontend

This React/Vite application is the frontend for the Multimodal Construction Intelligence Platform. For complete prerequisites, backend setup, API contracts, testing, deployment guidance, and limitations, see the [project README](../README.md).

Run the frontend from this directory:

```powershell
npm ci
npm run dev
```

In local development, the frontend defaults to `http://127.0.0.1:8000`. Production builds default to the deployed Render API at `https://multimodal-construction-intelligence-5yrh.onrender.com`. To override either base URL, set `VITE_API_BASE_URL` in `.env.local` for local development or in the Vercel project's environment variables for production, then rebuild/redeploy. Set the value to the API origin only (no endpoint path); all workflow paths and the health check are appended by the frontend. Vite variables are public—never put API keys or other credentials in them.
