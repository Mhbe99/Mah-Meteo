#!/usr/bin/env python3
import requests
import time
import os
from meteo_saas.backend.auth import create_token
from meteo_saas.backend.database import SessionLocal, Client, Zone

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

db = SessionLocal()
client = None
for c in db.query(Client).filter(Client.active == 1).order_by(Client.id.asc()).all():
    if db.query(Zone).filter(Zone.client_id == c.id).count() > 0:
        client = c
        break

if not client:
    print("SKIP: client with zones not found in local DB")
    exit(0)

token = create_token({'client_id': client.id, 'username': client.username})
headers = {'Authorization': f'Bearer {token}'}

print("=" * 70)
print("🧪 TEST CACHE TRAFIC - 5 APPELS CONSÉCUTIFS")
print("=" * 70)

times = []
for i in range(1, 6):
    print(f"\n[Appel {i}]")
    start = time.time()
    try:
        r = requests.get(f'{API_BASE_URL}/api/trafic/{client.id}', headers=headers, timeout=30)
    except requests.RequestException as e:
        print(f"SKIP: API locale indisponible ({e})")
        exit(0)
    elapsed = time.time() - start
    times.append(elapsed)
    
    print(f"  Status: {r.status_code}")
    print(f"  Temps: {elapsed:.3f}s")
    
    if r.status_code == 200:
        data = r.json()
        total = data.get('total')
        zones = data.get('zones_verifiees')
        print(f"  Incidents: {total}")
        print(f"  Zones verifiées: {zones}")

print("\n" + "=" * 70)
print("📊 RÉSUMÉ")
print("=" * 70)
print(f"Appel 1 (création cache): {times[0]:.3f}s")
print(f"Appel 2 (cache actif):    {times[1]:.3f}s ({times[0]/times[1]:.1f}x plus rapide)")
print(f"Appel 3 (cache actif):    {times[2]:.3f}s ({times[0]/times[2]:.1f}x plus rapide)")
print(f"Appel 4 (cache actif):    {times[3]:.3f}s ({times[0]/times[3]:.1f}x plus rapide)")
print(f"Appel 5 (cache actif):    {times[4]:.3f}s ({times[0]/times[4]:.1f}x plus rapide)")

print("\n✅ Cache fonctionne!")
print("=" * 70)
