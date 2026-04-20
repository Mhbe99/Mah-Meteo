#!/usr/bin/env python3
"""Check: Vérifier seulement ce qui est sur le dashboard"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")

# Authentication
print("Authentification...")
r = requests.post(RENDER_URL + '/auth/login', json={'username': 'geodis-lemeux', 'password': 'demo1234'})
token = r.json()['access_token']
print("✅ Login OK\n")

# Retrieve data
print("Récupération des zones avec données...\n")
r = requests.get(RENDER_URL + '/api/meteo/1', headers={'Authorization': f'Bearer {token}'})
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
