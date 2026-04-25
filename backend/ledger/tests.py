import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Merchant, Payout
from .services import create_credit


class PayoutIdempotencyTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(name="Test Merchant")
        create_credit(self.merchant, 10_000, "seed")
        self.client = APIClient()

    def test_same_idempotency_key_returns_same_response(self):
        key = str(uuid.uuid4())
        payload = {"amount_paise": 5000, "bank_account_id": "bank-123"}
        headers = {"HTTP_X_MERCHANT_ID": str(self.merchant.id), "HTTP_IDEMPOTENCY_KEY": key}
        first = self.client.post("/api/v1/payouts", payload, format="json", **headers)
        second = self.client.post("/api/v1/payouts", payload, format="json", **headers)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(Payout.objects.count(), 1)


class PayoutConcurrencyTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(name="Concurrent Merchant")
        create_credit(self.merchant, 10_000, "seed")

    def test_second_large_payout_is_rejected_after_funds_are_held(self):
        client = APIClient()
        first = client.post(
            "/api/v1/payouts",
            {"amount_paise": 6000, "bank_account_id": "bank-xyz"},
            format="json",
            HTTP_X_MERCHANT_ID=str(self.merchant.id),
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        second = client.post(
            "/api/v1/payouts",
            {"amount_paise": 6000, "bank_account_id": "bank-xyz"},
            format="json",
            HTTP_X_MERCHANT_ID=str(self.merchant.id),
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Payout.objects.count(), 1)


class PayoutImmediateSettlementTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(name="Immediate Merchant")
        create_credit(self.merchant, 10_000, "seed")
        self.client = APIClient()

    @patch("ledger.services.random.random", side_effect=[0.8, 0.8, 0.8])
    def test_request_reaches_terminal_state_without_worker(self, _):
        response = self.client.post(
            "/api/v1/payouts",
            {"amount_paise": 2000, "bank_account_id": "bank-terminal"},
            format="json",
            HTTP_X_MERCHANT_ID=str(self.merchant.id),
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], Payout.FAILED)
        self.assertEqual(response.json()["attempts"], 3)
