# Deploy LeadDesk AI on Railway

This deployment keeps the application's existing SQLite storage and Docker architecture. It is intended for one low-traffic demonstration or one small business. Use one service replica because a SQLite database on a mounted volume cannot be shared safely between replicas.

Railway detects a root-level `Dockerfile`, injects a `PORT` variable, and supports a persistent Volume mounted into the running service. The application is already configured for all three.

## Before opening Railway

1. Run the product checks:

   ```powershell
   .venv\Scripts\python.exe -m pytest -q
   .venv\Scripts\ruff.exe check .
   ```

2. Generate an admin token and save it in a password manager:

   ```powershell
   .venv\Scripts\python.exe scripts\generate_admin_token.py
   ```

3. Create a **private** GitHub repository and push this product directory. Do not commit `.env`, `.venv`, runtime databases, exported leads, or customer secrets.

## Create the Railway service

1. Sign in to Railway using the GitHub account that can access the private repository.
2. Select **New Project → Deploy from GitHub repo**.
3. Select the LeadDesk repository and its production branch.
4. Confirm the build logs say Railway detected the root `Dockerfile`.
5. Keep the service at **one replica**.

## Attach persistent storage

1. On the project canvas, right-click the LeadDesk service.
2. Select **Attach Volume**.
3. Set the mount path to:

   ```text
   /app/runtime
   ```

Only the mounted directory survives redeployments. The application database must therefore remain at `/app/runtime/leaddesk.db`.

## Set Railway variables

Open the service's **Variables** tab and add:

```text
APP_ENV=production
ADMIN_TOKEN=PASTE_THE_GENERATED_SECRET
DATABASE_PATH=/app/runtime/leaddesk.db
BUSINESS_FILE=/app/data/business.json
KNOWLEDGE_FILE=/app/data/knowledge_base.json
STORE_CONVERSATIONS=true
RATE_LIMIT_PER_MINUTE=20
```

Optional variables:

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-luna
LEAD_WEBHOOK_URL=
CORS_ORIGINS=
```

Leave `OPENAI_API_KEY` unset for the first public demo. Never put an admin token or API key into the repository, website HTML, screenshots, or client messages.

## Configure and publish

1. Open **Service → Settings → Deploy**.
2. Set **Healthcheck Path** to `/health`.
3. Keep **Restart Policy** at **On Failure**, maximum 10 retries.
4. Enable serverless/app sleeping for the demonstration if available on the selected plan.
5. Open **Settings → Networking** and generate a Railway domain.
6. Visit `https://YOUR-DOMAIN/health`; confirm `status`, `storage`, and `environment` are `ok`, `ok`, and `production`.

## Production acceptance test

- [ ] Homepage loads over HTTPS without mixed-content warnings
- [ ] Every primary CTA opens the quote form
- [ ] Pricing question returns the approved $129 demonstration answer and one source
- [ ] Unknown question produces the safe fallback
- [ ] A fictional lead can be submitted
- [ ] `/admin` rejects a wrong token and accepts the production token
- [ ] Submitted lead appears after a page refresh
- [ ] Lead status changes persist after the service restarts
- [ ] Knowledge edits persist after the service restarts
- [ ] Mobile layout and floating `/widget.js` embed work
- [ ] No secrets or real customer data appear in screenshots or logs

## Cost and operational controls

- Configure Railway usage notifications and a hard spending limit.
- Keep one replica while using SQLite.
- Download a database backup after material demo changes and before platform migrations.
- A mounted volume causes brief deployment downtime; this is acceptable for an introductory demo.
- Migrate to PostgreSQL before adding replicas, multiple businesses, or higher-volume client traffic.

## Rollback

If a deployment fails its health check, inspect the deploy logs. The most common causes are a weak/missing `ADMIN_TOKEN`, a missing Volume, or an incorrect `DATABASE_PATH`. Restore the previous working deployment from Railway and do not delete the Volume.

