import time

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run payout processor in a loop"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Payout worker started"))
        while True:
            call_command("process_payouts")
            time.sleep(2)
