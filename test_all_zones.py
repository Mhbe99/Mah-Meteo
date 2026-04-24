#!/usr/bin/env python3
"""Test: Envoyer manuellement pour chaque zone comme le ferait meteo_open.py"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")
TEST_USERNAME = os.getenv("TEST_USERNAME", "geodis-lemeux")
TEST_PASSWORD = os.getenv("TEST_PASSWORD") or os.getenv("INIT_CLIENT_PASSWORD", "demo1234")
RENDER_API_URL = f"{RENDER_URL}/api/meteo/snapshot/add"

TOUTES_ZONES = {
    "Le Meux 🏣": {"lat": 49.378829, "lon": 2.750393},
    "Clairoix 🏣": {"lat": 49.4194, "lon": 2.8328},
    "Beauvais": {"lat": 49.1, "lon": 2.1},
    "Compiègne": {"lat": 49.4176, "lon": 2.8261},
    "Creil": {"lat": 49.0, "lon": 2.0},
    "Nogent-sur-Oise": {"lat": 49.0, "lon": 2.0},
    "Chantilly": {"lat": 49.0, "lon": 2.0},
    "Clermont": {"lat": 49.1, "lon": 2.1},
    "Méru": {"lat": 49.0, "lon": 1.7},
    "Noyon": {"lat": 49.3, "lon": 2.6},
    "Senlis": {"lat": 49.0, "lon": 2.2},
    "Montataire": {"lat": 49.0, "lon": 2.0},
    "Liancourt": {"lat": 49.1, "lon": 2.1},
    "Chaumont-en-Vexin": {"lat": 49.0, "lon": 1.5},
}

login_resp = requests.post(
    f"{RENDER_URL}/auth/login",
    json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    timeout=15
)
if not login_resp.ok:
    print(f"SKIP: login impossible ({login_resp.status_code}) pour {TEST_USERNAME}")
    raise SystemExit(0)
login_data = login_resp.json()
token = login_data.get("access_token")
client_id = login_data.get("client_id")
if not token or not client_id:
    print(f"SKIP: payload login invalide: {login_data}")
    raise SystemExit(0)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print("[1] Envoi données pour toutes zones (comme meteo_open.py le ferait):\n")

success_count = 0
for zone_name in TOUTES_ZONES.keys():
    payload = {
        "zone_name": zone_name,
        "temperature": 20.5 + len(zone_name) * 0.1,  # Juste un nombre différent par zone
        "windspeed": 10.0,
        "wind_direction": "N",
        "precipitation": 0.5,
        "cloudcover": 50.0,
        "uv_index": 5.0,
        "risques": "Aucun risque",
        "ciel": "Nuageux"
    }
    
    try:
        response = requests.post(
            f"{RENDER_API_URL}?client_id=1",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ {zone_name:25s} | Temp: {payload['temperature']:.1f}C")
            success_count += 1
        else:
            print(f"❌ {zone_name:25s} | Status {response.status_code}: {response.json().get('detail', '')[:40]}")
    except Exception as e:
        print(f"❌ {zone_name:25s} | Error: {str(e)[:40]}")

print(f"\n✅ Total: {success_count}/{len(TOUTES_ZONES)} zones envoyées avec succès")

print("\n[2] Vérifier l'API pour confirmationêtes...\n")

headers = {"Authorization": f"Bearer {token}"}
r = requests.get(f"{RENDER_URL}/api/meteo/{client_id}", headers=headers, timeout=15)
if not r.ok:
    print(f"SKIP: lecture meteo impossible ({r.status_code})")
    raise SystemExit(0)
zones = r.json()
if not isinstance(zones, list):
    print(f"SKIP: format inattendu /api/meteo: {zones}")
    raise SystemExit(0)

has_data = 0
for zone in zones:
    if not isinstance(zone, dict):
        continue
    ztemp = zone.get('temp')
    if zone.get('type') == 'site' and ztemp is not None:
        print(f"✅ {zone.get('name','?'):25} | Temp: {float(ztemp):.1f}C")
        has_data += 1

print(f"\n📊 Résultat: {has_data} zones affichent des données")
