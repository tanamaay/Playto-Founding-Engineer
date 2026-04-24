from django.contrib import admin

from .models import IdempotencyRecord, LedgerEntry, Merchant, Payout

admin.site.register(Merchant)
admin.site.register(LedgerEntry)
admin.site.register(Payout)
admin.site.register(IdempotencyRecord)
