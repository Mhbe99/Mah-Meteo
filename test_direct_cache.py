#!/usr/bin/env python3
"""
Test direct de la fonction get_incidents sans passer par l'API
"""

from meteo_saas.backend.trafic import get_incidents
from meteo_saas.backend.database import SessionLocal, Zone

print("=" * 70)
print("🧪 TEST DIRECT get_incidents()")
print("=" * 70)

db = SessionLocal()
zones_db = db.query(Zone).all()

zones_list = [
    {"name": z.name, "lat": z.lat, "lon": z.lon, "type": z.type} 
    for z in zones_db
]

print(f"\n[1] Zones chargées: {len(zones_list)}")
for z in zones_list[:3]:
    print(f"    - {z['name']} ({z['lat']}, {z['lon']})")

print("\n[2] Appel get_incidents(test_mode=False)...")
result = get_incidents(zones_list, test_mode=False)

print(f"\n[3] Résultats:")
print(f"    Total: {result.get('total')}")
print(f"    Max delay: {result.get('retard_max')}")
print(f"    Zones: {result.get('zones_verifiees')}")
print(f"    Incidents: {len(result.get('incidents', []))}")

print("\n[4] Vérification du cache...")
import os
if os.path.exists("exports/trafic_cache.json"):
    print("    ✅ Fichier cache créé!")
    import json
    with open("exports/trafic_cache.json") as f:
        cache = json.load(f)
    print(f"    Contient {len(cache.get('incidents', []))} incidents")
    print(f"    Timestamp: {cache.get('timestamp')}")
else:
    print("    ❌ Pas de fichier cache")

print("\n" + "=" * 70)
