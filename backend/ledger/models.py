from django.db import models
from django.db.models import Q
from django.utils import timezone


class Merchant(models.Model):
    name = models.CharField(max_length=120)
    balance_paise = models.BigIntegerField(default=0)
    held_balance_paise = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class LedgerEntry(models.Model):
    CREDIT = "credit"
    DEBIT = "debit"
    ENTRY_TYPES = ((CREDIT, "Credit"), (DEBIT, "Debit"))

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="ledger_entries")
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    amount_paise = models.BigIntegerField()
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Payout(models.Model):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    STATUSES = (
        (PENDING, "Pending"),
        (PROCESSING, "Processing"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
    )

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="payouts")
    bank_account_id = models.CharField(max_length=120)
    amount_paise = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=STATUSES, default=PENDING)
    attempts = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(default=timezone.now)
    idempotency_key = models.UUIDField()
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class IdempotencyRecord(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="idempotency_records")
    key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=255)
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "key"],
                condition=Q(is_active=True),
                name="unique_active_idempotency_key_per_merchant",
            )
        ]
