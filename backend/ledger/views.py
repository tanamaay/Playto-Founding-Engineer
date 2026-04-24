from django.db import OperationalError
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LedgerEntry, Merchant, Payout
from .serializers import PayoutRequestSerializer
from .services import create_payout_request


class MerchantDashboardView(APIView):
    def get(self, request, merchant_id):
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        recent_ledger = list(
            LedgerEntry.objects.filter(merchant=merchant).order_by("-created_at").values(
                "id", "entry_type", "amount_paise", "note", "created_at"
            )[:10]
        )
        payouts = list(
            Payout.objects.filter(merchant=merchant).order_by("-created_at").values(
                "id",
                "amount_paise",
                "bank_account_id",
                "status",
                "attempts",
                "failure_reason",
                "created_at",
                "updated_at",
            )[:20]
        )
        return Response(
            {
                "merchant": {
                    "id": merchant.id,
                    "name": merchant.name,
                    "balance_paise": merchant.balance_paise,
                    "held_balance_paise": merchant.held_balance_paise,
                    "available_balance_paise": merchant.balance_paise - merchant.held_balance_paise,
                },
                "recent_entries": recent_ledger,
                "payouts": payouts,
            }
        )


class PayoutCreateView(APIView):
    def post(self, request):
        merchant_id = request.headers.get("X-Merchant-Id")
        idempotency_key = request.headers.get("Idempotency-Key")
        if not merchant_id:
            return Response({"detail": "X-Merchant-Id header is required."}, status=400)
        if not idempotency_key:
            return Response({"detail": "Idempotency-Key header is required."}, status=400)

        serializer = PayoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            response_body, response_code = create_payout_request(
                merchant_id=int(merchant_id),
                amount_paise=serializer.validated_data["amount_paise"],
                bank_account_id=serializer.validated_data["bank_account_id"],
                idempotency_key=idempotency_key,
            )
        except OperationalError:
            return Response({"detail": "Request collision, please retry."}, status=409)
        return Response(response_body, status=response_code)
