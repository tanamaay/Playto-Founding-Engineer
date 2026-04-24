from django.urls import path

from .views import MerchantDashboardView, PayoutCreateView

urlpatterns = [
    path("payouts", PayoutCreateView.as_view(), name="payout-create"),
    path("merchants/<int:merchant_id>/dashboard", MerchantDashboardView.as_view(), name="merchant-dashboard"),
]
