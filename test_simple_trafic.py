#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from meteo_saas.backend.auth import create_token
from meteo_saas.backend.database import SessionLocal, Client

db = SessionLocal()
client = db.query(Client).filter(Client.username == 'geodis-lemeux').first()

if not client:
    print("Client not found")
    exit(1)

# Créer token
token = create_token({'client_id': client.id, 'username': client.username})
print(f"Token: {token[:50]}...")

# Test API
headers = {'Authorization': f'Bearer {token}'}
r = requests.get('http://localhost:8080/api/trafic/1', headers=headers, timeout=30)

print(f"\nStatus: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    total = data.get('total')
    delay = data.get('retard_max')
    zones = data.get('zones_verifiees')
    incidents = data.get('incidents', [])
    
    print(f"Total incidents: {total}")
    print(f"Max delay: {delay} min")
    print(f"Zones verifiees: {zones}")
    
    if incidents:
        print(f"\nPremier incident:")
        inc = incidents[0]
        print(f"  Route: {inc.get('route')}")
        print(f"  Description: {inc.get('description')}")
        print(f"  Severity: {inc.get('severity')}")
else:
    print(f"Error: {r.text}")
