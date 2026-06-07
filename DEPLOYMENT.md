# Deployment Guide — FreelanceShield

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000/app | Dashboard UI |
| http://localhost:8000/docs | API documentation |
| http://localhost:8000/health | Health check |

## Docker

```bash
docker build -t freelanceshield .
docker run -p 8000:8000 --env-file .env freelanceshield
```

With PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
# Update .env: DATABASE_URL=postgresql://freelanceshield:freelanceshield@localhost:5432/freelanceshield
python run.py
```

## Production Checklist

1. **Secrets** — Generate new 64-char hex values for `SESSION_SECRET`, `ENCRYPTION_KEY`, `PORTAL_HMAC_SECRET`
2. **Database** — Use PostgreSQL (`DATABASE_URL=postgresql://...`)
3. **Storage** — Set `STORAGE_BACKEND=s3` with AWS credentials
4. **Email** — Set `EMAIL_PROVIDER=resend` and `RESEND_API_KEY`
5. **Stripe** — Configure `STRIPE_SECRET_KEY`, price IDs, and webhook secret
6. **HTTPS** — Set `NODE_ENV=production` and `APP_URL=https://your-domain.com`
7. **Scheduler** — Keep `ENABLE_SCHEDULER=true` (runs inside the app process)

## Deploy to Railway

1. Push repo to GitHub
2. Create new Railway project → Deploy from GitHub
3. Add PostgreSQL plugin
4. Set environment variables from `.env.example`
5. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Deploy to Render

1. New Web Service → connect repo
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add PostgreSQL database and set `DATABASE_URL`

## Stripe Webhook Setup

1. In Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://your-domain.com/api/v1/webhooks/stripe`
3. Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
4. Copy signing secret to `STRIPE_WEBHOOK_SECRET`

## OAuth Integration Setup

Set client IDs/secrets in `.env` for each provider. Redirect URIs must match:

- FreshBooks: `{APP_URL}/api/v1/integrations/freshbooks/callback`
- QuickBooks: `{APP_URL}/api/v1/integrations/quickbooks/callback`
- Wave: `{APP_URL}/api/v1/integrations/wave/callback`

## Running Tests

```bash
ENABLE_SCHEDULER=false NODE_ENV=test pytest -v
```

## CI

GitHub Actions runs tests on push/PR — see `.github/workflows/ci.yml`.
