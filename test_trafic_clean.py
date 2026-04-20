#!/usr/bin/env python3
import requests
from meteo_saas.backend.auth import create_token
from meteo_saas.backend.database import SessionLocal, Client

db = SessionLocal()
client = db.query(Client).filter(Client.username == 'service-meteo').first()

if not client:
    print("Client service-meteo not found")
    exit(1)

print(f"Client ID: {client.id}")
print(f"Client username: {client.username}")

# Créer token
token = create_token({'client_id': client.id, 'username': client.username})
print(f"Token created: {token[:50]}...")

# Test API
headers = {'Authorization': f'Bearer {token}'}

print(f"\nAppel: GET /api/trafic/{client.id}")
r = requests.get(f'http://localhost:8080/api/trafic/{client.id}', headers=headers, timeout=30)

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
