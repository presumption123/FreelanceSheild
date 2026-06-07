# FreelanceShield

Late-payment enforcement SaaS for freelancers. Automates the escalation ladder from polite reminders to small claims court packets, with jurisdiction-aware legal documents and a full audit trail.

Built in **Python** with FastAPI, SQLAlchemy, ReportLab, and Stripe.

---

## How It Works

FreelanceShield follows a **layered architecture** — each layer has one job:

```
Browser (Dashboard / Portal)
        ↓ HTTP
   Routers (app/routers/)     ← Parse requests, return responses
        ↓
   Services (app/services/)   ← Business logic (invoices, escalation, billing)
        ↓
   Models (app/models/)        ← Database tables via SQLAlchemy
        ↓
   SQLite / PostgreSQL
```

### Core flow: overdue invoice → court packet

1. **Create a client and invoice** — manually, via CSV import, or synced from FreshBooks/Wave/QuickBooks
2. **Invoice goes overdue** — a daily background job updates `days_overdue` and status
3. **Start enforcement** — moves the invoice to `IN_ENFORCEMENT` and begins at `REMINDER_1`
4. **Escalation ladder** — each stage sends an email and may generate a PDF:

   ```
   REMINDER_1 → REMINDER_2 → REMINDER_3 → DEMAND_LETTER → FINAL_NOTICE → COURT_READY
   ```

5. **You approve each step** (or enable auto-advance per client)
6. **Documents** — demand letters and court packets are generated as PDFs, stored locally or on S3
7. **Audit trail** — every email, status change, and document is logged immutably for court evidence
8. **Client portal** — clients get a signed URL to view the invoice, pay, or submit a dispute

### Background jobs

APScheduler runs inside the app process:

| Job | Schedule | Purpose |
|-----|----------|---------|
| Daily overdue update | Midnight UTC | Updates `days_overdue`, marks SENT → OVERDUE |
| Auto-advance | Every hour | Advances escalations when client has auto-advance enabled |
| Queue worker | Every 60s | Sends queued emails, generates documents |

Jobs are stored in the `queued_jobs` table so they survive restarts.

---

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

| URL | What it is |
|-----|------------|
| http://localhost:8000/app | **Dashboard** — login, manage invoices, clients, billing |
| http://localhost:8000/docs | **API docs** — interactive Swagger UI |
| http://localhost:8000/portal/{id}/view?token=... | **Client portal** — public invoice view |

### First-time usage

1. Open http://localhost:8000/app
2. Sign up with a password (min 12 characters)
3. After signup, verify email — in dev, the verification token is returned in the signup API response. Run:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/verify-email?token=YOUR_TOKEN"
   ```
4. Log in, add a client, create an invoice, mark it sent, then click **Enforce**

---

## Features

### Spec 00–05 (Core)
- Invoice management with status machine
- Escalation engine with plan limits (Free: 3, Starter: 25, Pro: unlimited)
- Jurisdiction-aware demand letters and court packets (CA, NY, TX, FL, IL, UK)
- Session auth with Argon2id, email verification, password reset
- Immutable audit trail with PDF export

### Spec 06 — Integrations
- **CSV import** — `POST /api/v1/imports/csv` or upload via dashboard
- **FreshBooks / Wave / QuickBooks** — OAuth connect, sync invoices (`/api/v1/integrations/{provider}/...`)

### Spec 07 — Client Portal
- HMAC-signed portal URLs (90-day expiry, rotated on escalation)
- Payment links (Stripe + mailto fallback)
- Dispute submission with reason codes

### Spec 08 — Full REST API
- Auth, clients, invoices, escalations, documents, dashboard
- Settings (profile, export, account deletion)
- Audit logs, jurisdictions, billing, webhooks

### Spec 09 — Frontend
- Dashboard at `/app` — aging stats, invoice table, client management, CSV import, billing
- Client portal at `/portal/{id}/view?token=...`

### Spec 10 — Jobs & Queues
- Persistent job queue (`queued_jobs` table)
- APScheduler for cron-style and interval jobs
- Email and document generation workers

### Spec 11 — Billing
- Stripe Checkout for Starter ($15) and Pro ($25) plans
- Stripe Customer Portal for subscription management
- Webhook handler for plan upgrades/downgrades
- Usage metering (active enforcement case count)

### Spec 12 — Testing & Deployment
- pytest test suite (`tests/test_api.py`)
- GitHub Actions CI (`.github/workflows/ci.yml`)
- Dockerfile and `docker-compose.yml`
- See [DEPLOYMENT.md](DEPLOYMENT.md) for production setup

---

## Project Structure

```
app/
├── main.py              # App entry — mounts routers, starts scheduler
├── config.py            # Environment variables (validated with Pydantic)
├── database.py          # SQLAlchemy engine and sessions
├── models/              # Database tables (User, Invoice, Escalation, etc.)
├── schemas/             # Request/response validation (Pydantic)
├── constants/           # Escalation stages, plan limits
├── legal_templates/     # Per-state/UK jurisdiction configs
├── lib/                 # Password hashing, encryption, portal tokens, S3 storage
├── services/            # Business logic (no HTTP knowledge)
├── routers/             # HTTP endpoints
├── jobs/                # Scheduler and background workers
└── web/                 # Dashboard and portal HTML/CSS/JS
tests/                   # pytest tests
Dockerfile               # Production container
docker-compose.yml       # Local Postgres + Redis
```

---

## Configuration

Copy `.env.example` to `.env`. Key variables:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLite (dev) or PostgreSQL (production) |
| `SESSION_SECRET` | 64-char hex — signs session cookies |
| `ENCRYPTION_KEY` | 64-char hex — encrypts OAuth tokens at rest |
| `PORTAL_HMAC_SECRET` | 64-char hex — signs client portal URLs |
| `STRIPE_SECRET_KEY` | Enables billing (leave empty to disable) |
| `EMAIL_PROVIDER` | `console` (logs to terminal), `resend`, or `sendgrid` |
| `STORAGE_BACKEND` | `local` (dev) or `s3` (production) |
| `ENABLE_SCHEDULER` | `true` to run background jobs in-process |

---

## Publishing / Deploying

### Option 1: Docker (recommended)

```bash
docker build -t freelanceshield .
docker run -p 8000:8000 --env-file .env freelanceshield
```

### Option 2: Railway / Render

1. Push to GitHub
2. Connect repo to Railway or Render
3. Add PostgreSQL
4. Set env vars from `.env.example`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Full details: [DEPLOYMENT.md](DEPLOYMENT.md)

### Stripe setup (for billing)

1. Create products/prices in Stripe Dashboard
2. Set `STRIPE_STARTER_PRICE_ID` and `STRIPE_PRO_PRICE_ID` in `.env`
3. Add webhook endpoint: `https://your-domain.com/api/v1/webhooks/stripe`

---

## API Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/signup` | Create account |
| POST | `/api/v1/auth/login` | Login (sets session cookie) |
| GET | `/api/v1/dashboard/summary` | Aging dashboard data |
| POST | `/api/v1/clients` | Add client |
| POST | `/api/v1/invoices` | Create invoice |
| POST | `/api/v1/imports/csv` | Import invoices from CSV |
| POST | `/api/v1/integrations/{provider}/sync` | Sync from accounting app |
| POST | `/api/v1/escalations/{id}/start` | Start enforcement |
| POST | `/api/v1/escalations/{id}/advance` | Advance to next stage |
| POST | `/api/v1/documents/invoices/{id}/demand-letter` | Generate demand letter PDF |
| POST | `/api/v1/documents/invoices/{id}/court-packet` | Generate court packet PDF |
| GET | `/api/v1/audit?invoiceId=...` | Audit trail |
| POST | `/api/v1/billing/checkout?plan=STARTER` | Stripe checkout |
| GET | `/api/v1/portal/{id}?token=...` | Client portal data |

---

## Pricing Tiers

| Plan | Price | Active enforcement cases |
|------|-------|--------------------------|
| Free | $0 | 3 |
| Starter | $15/mo | 25 |
| Pro | $25/mo | Unlimited |

---

## Running Tests

```bash
ENABLE_SCHEDULER=false NODE_ENV=test pytest -v
```

---

## License

Proprietary — see project owner.
