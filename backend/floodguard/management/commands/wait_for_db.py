"""
wait_for_db management command.
Retries DB connection until healthy (used in Docker Compose startup).
"""
import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Wait for the database to be available."

    def handle(self, *args, **options):
        self.stdout.write("Waiting for database...")
        db_conn = None
        attempts = 0
        while not db_conn:
            try:
                db_conn = connections["default"]
                db_conn.ensure_connection()
                self.stdout.write(self.style.SUCCESS("Database available!"))
            except OperationalError:
                attempts += 1
                self.stdout.write(f"Database unavailable, waiting 1s... (attempt {attempts})")
                time.sleep(1)
                if attempts >= 60:
                    self.stderr.write(self.style.ERROR("Database not available after 60s. Exiting."))
                    raise SystemExit(1)
