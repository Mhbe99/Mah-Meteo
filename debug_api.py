#!/usr/bin/env python3
"""Debug: Vérifier directement l'API Render"""
import requests
import json

RENDER_URL = 'https://mah-meteo.onrender.com'

import os
from dotenv import load_dotenv
load_dotenv()

# Login
print("[1] Authentification...")
r = requests.post(RENDER_URL + '/auth/login', json={
    'username': os.getenv('TEST_USERNAME', 'service-meteo'),
    'password': os.getenv('TEST_PASSWORD', '')
})
if r.status_code != 200:
    print(f'❌ Login failed: {r.status_code}')
    print(r.text)
    exit(1)
token = r.json()['access_token']
print('✅ Token obtenu')

# Get raw zones
print("\n[2] Récupération zones brutes...")
r = requests.get(RENDER_URL + '/api/meteo/1', headers={'Authorization': f'Bearer {token}'})
print(f"Status: {r.status_code}")
zones = r.json()
print(f"Nombre de zones: {len(zones)}")

# Afficher les 3 premières zones complètement
print("\n[3] Les 3 premières zones (JSON complet):")
for i, zone in enumerate(zones[:3]):
    print(f"\nZone {i+1} ({zone.get('name', '?')}):")
    print(json.dumps(zone, indent=2, ensure_ascii=False))

# Compter combien ont des données
print("\n[4] Zones avec données:")
sites_with_data = 0
for zone in zones:
    if zone['type'] == 'site' and zone.get('temp') is not None:
        sites_with_data += 1
        print(f"  ✅ {zone['name']}: temp={zone.get('temp')}")

if sites_with_data == 0:
    print("  ⚠️ Aucune zone avec données")

print(f"\nTotal: {sites_with_data} zones avec données")
