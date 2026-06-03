#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import os
from meteo_saas.backend.auth import create_token
from meteo_saas.backend.database import SessionLocal, Client, Zone

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

db = SessionLocal()

# Prendre un client actif qui possède au moins une zone
client = db.query(Client).filter(Client.active == 1).order_by(Client.id.asc()).first()
if client:
    zone_count = db.query(Zone).filter(Zone.client_id == client.id).count()
    if zone_count == 0:
        client = None
        for c in db.query(Client).filter(Client.active == 1).order_by(Client.id.asc()).all():
            if db.query(Zone).filter(Zone.client_id == c.id).count() > 0:
                client = c
                break

if not client:
    print("SKIP: client with zones not found in local DB")
    exit(0)

# Créer token
token = create_token({'client_id': client.id, 'username': client.username})
print(f"Token: {token[:50]}...")

# Test API
headers = {'Authorization': f'Bearer {token}'}
try:
    r = requests.get(f'{API_BASE_URL}/api/trafic/{client.id}', headers=headers, timeout=30)
except requests.RequestException as e:
    print(f"SKIP: API unreachable at {API_BASE_URL} ({e})")
    exit(0)

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
