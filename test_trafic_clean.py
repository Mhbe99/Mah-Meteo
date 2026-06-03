#!/usr/bin/env python3
import requests
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

print(f"Client ID: {client.id}")
print(f"Client username: {client.username}")

# Créer token
token = create_token({'client_id': client.id, 'username': client.username})
print(f"Token created: {token[:50]}...")

# Test API
headers = {'Authorization': f'Bearer {token}'}

print(f"\nAppel: GET /api/trafic/{client.id}")
try:
    r = requests.get(f'{API_BASE_URL}/api/trafic/{client.id}', headers=headers, timeout=30)
except requests.RequestException as e:
    print(f"SKIP: API unreachable at {API_BASE_URL} ({e})")
    exit(0)

print(f"Status: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    total = data.get('total')
    delay = data.get('retard_max')
    zones = data.get('zones_verifiees')
    
    print(f"SUCCESS!")
    print(f"  Total incidents: {total}")
    print(f"  Max delay: {delay} min")
    print(f"  Zones: {zones}")
else:
    print(f"Error response: {r.text[:200]}")
