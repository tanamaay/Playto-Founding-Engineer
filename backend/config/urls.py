from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse

urlpatterns = [
    path("", lambda request: JsonResponse({"ok": True, "service": "ledger-api"})),
    path("admin/", admin.site.urls),
    path("api/v1/", include("ledger.urls")),
]
