# ConstructAI frontend

This React/Vite application is the frontend for the Multimodal Construction Intelligence Platform. For complete prerequisites, backend setup, API contracts, testing, deployment guidance, and limitations, see the [project README](../README.md).

Run the frontend from this directory:

```powershell
npm ci
npm run dev
```

The frontend calls `http://127.0.0.1:8000` by default. Override the public API origin at build time with `VITE_API_BASE_URL` in `.env.local`; do not put credentials in Vite environment variables.
