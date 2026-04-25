from django.urls import path
from django.http import JsonResponse

from .views import MerchantDashboardView, PayoutCreateView

urlpatterns = [
    path("", lambda request: JsonResponse({"ok": True, "service": "ledger-api", "version": "v1"}), name="api-root"),
    path("payouts", PayoutCreateView.as_view(), name="payout-create"),
    path("merchants/<int:merchant_id>/dashboard", MerchantDashboardView.as_view(), name="merchant-dashboard"),
]
