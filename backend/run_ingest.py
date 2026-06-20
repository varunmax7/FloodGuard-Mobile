import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "floodguard.settings")
django.setup()

from apps.ingest.tasks import ingest_ecmwf, ingest_aws, ingest_radar, recompute_bias

print("Running ECMWF..."); r1 = ingest_ecmwf.apply().get(); print(f"  → {r1} stages written")
print("Running AWS..."); r2 = ingest_aws.apply().get(); print(f"  → {r2} observations written")
print("Running Radar..."); r3 = ingest_radar.apply().get(); print(f"  → {r3} frame written")
print("Running Bias..."); r4 = recompute_bias.apply().get(); print(f"  → {r4} bias factors written")
print("\nAll done!")
