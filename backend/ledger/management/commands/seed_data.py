from django.core.management.base import BaseCommand
from django.db import transaction

from ledger.models import Merchant
from ledger.services import create_credit


class Command(BaseCommand):
    help = "Seed merchants and credit history"

    @transaction.atomic
    def handle(self, *args, **options):
        data = [
            ("North Mart", [100_000, 40_000, 55_000]),
            ("Blue Bazaar", [220_000, 30_000]),
            ("Urban Foods", [75_000, 95_000, 10_000]),
        ]
        for merchant_name, credits in data:
            merchant, _ = Merchant.objects.get_or_create(name=merchant_name)
            if merchant.balance_paise == 0:
                for idx, amount in enumerate(credits, start=1):
                    create_credit(merchant, amount, f"Seed credit #{idx}")
        self.stdout.write(self.style.SUCCESS("Seeded merchants with ledger history"))
