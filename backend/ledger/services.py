import hashlib
import random
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import IdempotencyRecord, LedgerEntry, Merchant, Payout

ALLOWED_TRANSITIONS = {
    Payout.PENDING: {Payout.PROCESSING},
    Payout.PROCESSING: {Payout.COMPLETED, Payout.FAILED},
    Payout.COMPLETED: set(),
    Payout.FAILED: set(),
}


def request_fingerprint(amount_paise: int, bank_account_id: str) -> str:
    return hashlib.sha256(f"{amount_paise}:{bank_account_id}".encode("utf-8")).hexdigest()


def get_or_create_idempotency(merchant: Merchant, key: str, fingerprint: str):
    now = timezone.now()
    IdempotencyRecord.objects.filter(
        merchant=merchant, key=key, is_active=True, expires_at__lte=now
    ).update(is_active=False)
    existing = IdempotencyRecord.objects.filter(merchant=merchant, key=key, is_active=True).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            return None, {"detail": "Idempotency key reused with different payload."}, 409
        if existing.response_body is not None:
            return existing, existing.response_body, existing.response_code
        return existing, {"detail": "Request already in flight."}, 409

    try:
        record = IdempotencyRecord.objects.create(
            merchant=merchant,
            key=key,
            request_fingerprint=fingerprint,
            expires_at=now + timedelta(hours=24),
        )
    except IntegrityError:
        record = IdempotencyRecord.objects.get(merchant=merchant, key=key, is_active=True)
        return record, record.response_body, record.response_code
    return record, None, None


def transition_or_raise(payout: Payout, to_status: str) -> None:
    if to_status not in ALLOWED_TRANSITIONS[payout.status]:
        raise ValueError(f"Illegal state transition {payout.status} -> {to_status}")


def create_credit(merchant: Merchant, amount_paise: int, note: str) -> None:
    LedgerEntry.objects.create(merchant=merchant, entry_type=LedgerEntry.CREDIT, amount_paise=amount_paise, note=note)
    Merchant.objects.filter(pk=merchant.pk).update(balance_paise=F("balance_paise") + amount_paise)


def ledger_balance_query(merchant_id: int):
    return (
        LedgerEntry.objects.filter(merchant_id=merchant_id)
        .aggregate(
            credits=Coalesce(Sum("amount_paise", filter=Q(entry_type=LedgerEntry.CREDIT)), Value(0)),
            debits=Coalesce(Sum("amount_paise", filter=Q(entry_type=LedgerEntry.DEBIT)), Value(0)),
        )
    )


@transaction.atomic
def create_payout_request(merchant_id: int, amount_paise: int, bank_account_id: str, idempotency_key: str):
    merchant = Merchant.objects.select_for_update().get(pk=merchant_id)
    fingerprint = request_fingerprint(amount_paise, bank_account_id)
    idem, body, code = get_or_create_idempotency(merchant, idempotency_key, fingerprint)
    if body is not None:
        return body, code

    updated = Merchant.objects.filter(
        pk=merchant.pk, balance_paise__gte=F("held_balance_paise") + amount_paise
    ).update(held_balance_paise=F("held_balance_paise") + amount_paise)
    if not updated:
        response = {"detail": "Insufficient available balance."}
        idem.response_body = response
        idem.response_code = 400
        idem.save(update_fields=["response_body", "response_code"])
        return response, 400

    payout = Payout.objects.create(
        merchant=merchant,
        bank_account_id=bank_account_id,
        amount_paise=amount_paise,
        status=Payout.PENDING,
        idempotency_key=idempotency_key,
    )
    response = {
        "id": payout.id,
        "merchant_id": payout.merchant_id,
        "amount_paise": payout.amount_paise,
        "bank_account_id": payout.bank_account_id,
        "status": payout.status,
        "attempts": payout.attempts,
    }
    idem.response_body = response
    idem.response_code = 201
    idem.save(update_fields=["response_body", "response_code"])
    return response, 201


def resolve_processing_payout(payout: Payout):
    if payout.status == Payout.PENDING:
        transition_or_raise(payout, Payout.PROCESSING)
        payout.status = Payout.PROCESSING
    elif payout.status != Payout.PROCESSING:
        raise ValueError(f"Unexpected status {payout.status}")

    payout.attempts += 1
    payout.next_retry_at = timezone.now() + timedelta(seconds=30 * (2 ** (payout.attempts - 1)))
    payout.save(update_fields=["status", "attempts", "next_retry_at", "updated_at"])

    roll = random.random()
    if roll < 0.7:
        with transaction.atomic():
            locked = Payout.objects.select_for_update().get(pk=payout.pk)
            transition_or_raise(locked, Payout.COMPLETED)
            merchant_updated = Merchant.objects.filter(pk=locked.merchant_id).update(
                held_balance_paise=F("held_balance_paise") - locked.amount_paise,
                balance_paise=F("balance_paise") - locked.amount_paise,
            )
            if merchant_updated != 1:
                raise ValueError("Merchant update failed")
            LedgerEntry.objects.create(
                merchant_id=locked.merchant_id,
                entry_type=LedgerEntry.DEBIT,
                amount_paise=locked.amount_paise,
                note=f"Payout #{locked.id} completed",
            )
            locked.status = Payout.COMPLETED
            locked.failure_reason = ""
            locked.save(update_fields=["status", "failure_reason", "updated_at"])
        return

    if roll < 0.9:
        if payout.attempts >= 3:
            fail_payout(payout.id, "Bank timed out repeatedly")
        return

    fail_payout(payout.id, "Bank settlement failed")


def fail_payout(payout_id: int, reason: str):
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(pk=payout_id)
        transition_or_raise(payout, Payout.FAILED)
        Merchant.objects.filter(pk=payout.merchant_id).update(
            held_balance_paise=F("held_balance_paise") - payout.amount_paise
        )
        payout.status = Payout.FAILED
        payout.failure_reason = reason
        payout.save(update_fields=["status", "failure_reason", "updated_at"])
