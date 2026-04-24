# EXPLAINER

## 1) The Ledger

Balance calculation query:

```python
LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
    credits=Coalesce(Sum("amount_paise", filter=Q(entry_type=LedgerEntry.CREDIT)), Value(0)),
    debits=Coalesce(Sum("amount_paise", filter=Q(entry_type=LedgerEntry.DEBIT)), Value(0)),
)
```

Modeling choice:
- `LedgerEntry` stores immutable credit/debit rows in paise (`BigIntegerField`) for auditability.
- `Merchant.balance_paise` is the running finalized balance for fast reads.
- `Merchant.held_balance_paise` tracks temporary payout holds.
- Displayed available balance is `balance_paise - held_balance_paise`.

## 2) The Lock

Code that prevents two concurrent payouts from overdrawing:

```python
updated = Merchant.objects.filter(
    pk=merchant.pk, balance_paise__gte=F("held_balance_paise") + amount_paise
).update(held_balance_paise=F("held_balance_paise") + amount_paise)
```

Why this works:
- It is a single SQL `UPDATE ... WHERE` statement with `F()` expressions.
- The check and hold happen atomically in the database, not in Python.
- If funds are insufficient at write time, `updated == 0` and request is rejected.

## 3) The Idempotency

How key dedupe works:
- `IdempotencyRecord` stores `(merchant, key, request_fingerprint, response_code, response_body, expires_at)`.
- Unique active constraint is per merchant+key.
- On request, expired active keys are deactivated; then active key is checked.
- If same key + same payload exists with stored response, API returns the exact same JSON + status.
- If same key but different payload, API returns `409`.
- If first request is still in flight and response is not stored yet, second request returns `409`.

## 4) The State Machine

Transition guard:

```python
ALLOWED_TRANSITIONS = {
    Payout.PENDING: {Payout.PROCESSING},
    Payout.PROCESSING: {Payout.COMPLETED, Payout.FAILED},
    Payout.COMPLETED: set(),
    Payout.FAILED: set(),
}

def transition_or_raise(payout: Payout, to_status: str) -> None:
    if to_status not in ALLOWED_TRANSITIONS[payout.status]:
        raise ValueError(f"Illegal state transition {payout.status} -> {to_status}")
```

Failed-to-completed is blocked because `ALLOWED_TRANSITIONS[Payout.FAILED]` is an empty set.

## 5) The AI Audit

One subtle wrong code example:
- Wrong AI suggestion used: `Sum("amount_paise", filter=F("entry_type") == LedgerEntry.CREDIT)`.
- Problem: `F("entry_type") == ...` is Python-level comparison and does not build the correct SQL filter predicate.
- Fix used: `filter=Q(entry_type=LedgerEntry.CREDIT)` and similarly for debits.

What I replaced it with:

```python
credits=Coalesce(Sum("amount_paise", filter=Q(entry_type=LedgerEntry.CREDIT)), Value(0))
debits=Coalesce(Sum("amount_paise", filter=Q(entry_type=LedgerEntry.DEBIT)), Value(0))
```
