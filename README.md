# Merchant Ledger and Payout System

This repository contains:
- A Django backend for merchant ledgering, payout requests, idempotency, and payout processing
- A React dashboard for balances, ledger history, payout creation, and live payout status refresh

## Tech stack

- Backend: Django + Django REST Framework
- Frontend: React + Vite
- Data: SQLite for local setup (PostgreSQL recommended for production-grade row locking)

## Backend setup

```bash
cd backend
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

In a second terminal, run the payout worker:

```bash
cd backend
python manage.py run_payout_worker
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## API endpoints

- `POST /api/v1/payouts`
  - Headers:
    - `X-Merchant-Id: <merchant_id>`
    - `Idempotency-Key: <uuid>`
  - Body:
    - `amount_paise` (integer)
    - `bank_account_id` (string)

- `GET /api/v1/merchants/<merchant_id>/dashboard`
  - Returns merchant balances, recent ledger entries, and payout history

## Notes on assignment constraints

- Money uses integer paise in `BigIntegerField`.
- Payout request hold logic uses DB-level `F()` updates for atomic balance checks and holds.
- Idempotency keys are scoped per merchant with 24-hour active window.
- State transitions are guarded by an explicit transition map.
- Failed payouts atomically release held funds.
- Retry uses exponential backoff (`30s`, `60s`, `120s`) with max 3 attempts, then fail.

## Tests

```bash
cd backend
python manage.py test
```

Included tests:
- Idempotency behavior (`same key => same response`)
- Overdraw protection after fund hold

## Deployment

Deploy backend to Render/Railway/Fly.io and frontend to Vercel/Netlify.
Set frontend API base URL to your deployed backend host.
