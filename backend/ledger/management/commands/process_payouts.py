from django.core.management.base import BaseCommand
from django.utils import timezone

from ledger.models import Payout
from ledger.services import resolve_processing_payout


class Command(BaseCommand):
    help = "Process pending/processing payouts and settle them"

    def handle(self, *args, **options):
        now = timezone.now()
        payouts = Payout.objects.filter(
            status__in=[Payout.PENDING, Payout.PROCESSING],
            next_retry_at__lte=now,
        ).order_by("created_at")[:50]

        for payout in payouts:
            try:
                resolve_processing_payout(payout)
                self.stdout.write(self.style.SUCCESS(f"Processed payout {payout.id}"))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Payout {payout.id} failed: {exc}"))
