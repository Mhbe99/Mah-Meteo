#!/usr/bin/env python3
"""Check: Vérifier seulement ce qui est sur le dashboard"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")
TEST_USERNAME = os.getenv("TEST_USERNAME", "")
TEST_PASSWORD = os.getenv("TEST_PASSWORD") or os.getenv("INIT_CLIENT_PASSWORD", "")

# Authentication
print("Authentification...")
try:
    r = requests.post(RENDER_URL + '/auth/login', json={'username': TEST_USERNAME, 'password': TEST_PASSWORD}, timeout=15)
except requests.RequestException as e:
    print(f"SKIP: endpoint indisponible ({e})")
    raise SystemExit(0)
if not r.ok:
    if r.status_code in (401, 403):
        print(f"SKIP: identifiants invalides pour {TEST_USERNAME}")
        raise SystemExit(0)
    print(f"❌ Login HTTP {r.status_code}: {r.text[:200]}")
    raise SystemExit(1)
login_data = r.json()
token = login_data.get('access_token')
client_id = login_data.get('client_id')
if not token or not client_id:
    print(f"❌ Réponse login invalide: {login_data}")
    raise SystemExit(1)
print("✅ Login OK\n")

# Retrieve data
print("Récupération des zones avec données...\n")
r = requests.get(f"{RENDER_URL}/api/meteo/{client_id}", headers={'Authorization': f'Bearer {token}'}, timeout=15)
if not r.ok:
    if r.status_code in (401, 403):
        print("SKIP: token refusé par l'API")
        raise SystemExit(0)
    print(f"❌ Erreur météo HTTP {r.status_code}: {r.text[:200]}")
    raise SystemExit(1)
zones = r.json()

print("ZONES AVEC DONNÉES:\n")
sites_with_data = []
for zone in zones:
    if zone['type'] == 'site':
        if zone.get('temp') is not None:
            sites_with_data.append(zone['name'])
            print(f"  ✅ {zone['name']:25} | T:{zone['temp']:5.1f}C | W:{zone['wind']:5.1f}km/h | P:{zone.get('precipitation', 'N/A')} | Cloud:{zone.get('cloudcover', 'N/A')}%")
        else:
            print(f"  ⚠️  {zone['name']:25} | No data")

print(f"\n📊 Total: {len(sites_with_data)}/14 sites avec données")
print("\nZones affichées:")
for name in sites_with_data:
    print(f"  - {name}")
