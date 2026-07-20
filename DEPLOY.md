# Deploying to Vercel (frontend) + Render (backend)

This app is split for hosting:

- **Frontend** — Vite/React static build → **Vercel**
- **Backend** — FastAPI (stateful: DB, file uploads, admin edits, SSE) → **Render**
  (a persistent host, unlike Vercel's read-only serverless filesystem)

The frontend calls the backend at build time via `VITE_API_URL`. So deploy the
**backend first**, grab its URL, then deploy the frontend.

---

## 1. Backend on Render

1. Push this repo to GitHub (already done: `kaushikagate22-sys/Claims-Processing`).
2. In [Render](https://dashboard.render.com) → **New +** → **Blueprint** → connect
   the repo. Render reads [`render.yaml`](render.yaml) and creates the
   `agentic-claims-api` web service (build installs deps + seeds the DB; start
   runs uvicorn).
3. When prompted, set env vars:
   - `ALLOWED_ORIGINS` — leave a placeholder for now (e.g. `https://placeholder`),
     you'll set the real Vercel URL in step 3.
   - *(optional)* `OPENAI_API_KEY` **or** `ANTHROPIC_API_KEY` to enable the real
     LLM. Omit both to run the deterministic **offline** mode.
4. Deploy. Note the service URL, e.g. `https://agentic-claims-api.onrender.com`.
   Verify: open `…/health` → `{"status":"ok",...}`.

> **Free-tier caveat (important):** Render's free plan has an **ephemeral
> filesystem** and spins the service down after ~15 min idle. The SQLite
> `claims.db` and any uploaded files **reset to the seeded state** on each deploy
> and cold start. Seeded policy/history data always returns (re-seeded at build);
> *runtime* claims and uploads do not persist. Fine for a demo.
>
> **For real persistence:** uncomment the `databases:` block and the `DATABASE_URL`
> env var in [`render.yaml`](render.yaml) (Render Postgres), or point
> `DATABASE_URL` at your Azure Postgres. No code changes — the DB layer is already
> `DATABASE_URL`-driven. (Uploaded *files* would still need blob storage; the DB
> covers claim records/decisions.)

---

## 2. Frontend on Vercel

1. In [Vercel](https://vercel.com/new) → **Add New… → Project** → import the repo.
2. **Root Directory:** set to **`frontend`** (the app lives in that subfolder).
   Vercel auto-detects Vite from [`frontend/vercel.json`](frontend/vercel.json).
3. **Environment Variables** → add:
   - `VITE_API_URL` = your Render URL from step 1, **no trailing slash**
     (e.g. `https://agentic-claims-api.onrender.com`).
4. **Deploy.** Note the assigned URL, e.g. `https://your-app.vercel.app`.

---

## 3. Close the CORS loop

Back in Render → the service → **Environment** → set:

- `ALLOWED_ORIGINS` = your Vercel URL (e.g. `https://your-app.vercel.app`).
  Add your custom domain too, comma-separated, if you have one.

Save → Render redeploys. Done — open the Vercel URL.

> Any time the frontend or backend URL changes, update the matching var
> (`VITE_API_URL` on Vercel triggers a rebuild; `ALLOWED_ORIGINS` on Render
> triggers a redeploy).

---

## Alternative: backend on Railway

Same idea, no blueprint file needed:

1. [Railway](https://railway.app) → **New Project → Deploy from GitHub repo**.
2. Set **Start Command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
3. Set env vars: `ALLOWED_ORIGINS`, optional LLM key, optional `DATABASE_URL`.
   (Railway provides a one-click Postgres plugin that sets `DATABASE_URL` for you —
   giving persistence out of the box.)
4. Run the seed once from the Railway shell: `python scripts/seed_db.py`.
5. Use the generated Railway URL as `VITE_API_URL` on Vercel.

---

## Why not the whole thing on Vercel?

Vercel's Python runtime is serverless: stateless, read-only filesystem (except
`/tmp`, wiped between requests). This backend writes SQLite, saves uploaded
claim files/photos it serves back later, lets admins overwrite `rules.yaml` /
master CSVs on disk, and streams SSE. Those need a persistent process — hence
Render/Railway for the API, Vercel for the static frontend.
