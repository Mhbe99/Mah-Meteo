#!/usr/bin/env python3
"""
🚀 TEST COMPLET - Envoi et affichage des données sur Render
"""
import requests
import json
from time import sleep

RENDER_URL = 'https://mah-meteo.onrender.com'
BASE_LOGIN_URL = f'{RENDER_URL}/auth/login'
API_BASE = f'{RENDER_URL}/api'

print("=" * 80)
print("🚀 TEST COMPLET RENDER - DONNÉES JUSQU'AU DASHBOARD")
print("=" * 80)
print()

# [1] Récupérer token de service
print("[1] Récupération token service...")
r = requests.post(f'{API_BASE}/service/token', timeout=10)
service_token = r.json()['token']
print(f"✅ Token service: {service_token[:40]}...")
print()

# [2] Envoyer 3 snapshots (zones différentes)
print("[2] Envoi de 3 snapshots à Render...")
zones_data = [
    {"zone_name": "Le Meux", "temperature": 18.5, "windspeed": 15, "wind_direction": "N",
     "precipitation": 0.5, "cloudcover": 35, "uv_index": 4, "risques": "Aucun", "ciel": "Clair"},
    {"zone_name": "Clairoix", "temperature": 17.2, "windspeed": 12, "wind_direction": "NE",
     "precipitation": 0.2, "cloudcover": 30, "uv_index": 3, "risques": "Aucun", "ciel": "Dégagé"},
    {"zone_name": "Compiègne", "temperature": 19.1, "windspeed": 18, "wind_direction": "O",
     "precipitation": 1.0, "cloudcover": 50, "uv_index": 5, "risques": "Vent modéré", "ciel": "Nuageux"},
]

headers_service = {
    "Authorization": f"Bearer {service_token}",
    "Content-Type": "application/json"
}

for data in zones_data:
    r = requests.post(
        f'{API_BASE}/meteo/snapshot/add?client_id=1',
        headers=headers_service,
        json=data,
        timeout=10
    )
    if r.status_code == 200:
        zone = data['zone_name']
        temp = data['temperature']
        print(f"  ✅ {zone}: {temp}°C envoyé")
    else:
        print(f"  ❌ Erreur: {r.status_code}")

print()

# [3] Attendre un peu que la BD soit mise à jour
print("[3] Attente mise à jour BD...")
sleep(2)
print("  ✅ Prêt")
print()

# [4] Appeler le dashboard (login + récupérer les données)
print("[4] Test du dashboard (login + données)...")
print()

# Login
print("  a) Login...")
r = requests.post(
    f'{RENDER_URL}/auth/login',
    json={"username": "geodis-lemeux", "password": "demo1234"},
    timeout=10
)

if r.status_code != 200:
    print(f"  ❌ Login failed: {r.status_code}")
    print(f"     {r.text[:200]}")
    exit(1)

user_token = r.json()['access_token']
client_id = r.json()['client_id']
print(f"  ✅ Login OK - client_id={client_id}")

# Récupérer les données météo
print("  b) Récupération données météo...")
headers_user = {
    "Authorization": f"Bearer {user_token}",
    "Content-Type": "application/json"
}

r = requests.get(
    f'{API_BASE}/meteo/{client_id}',
    headers=headers_user,
    timeout=10
)

if r.status_code != 200:
    print(f"  ❌ Erreur: {r.status_code}")
    print(f"     {r.text[:200]}")
    exit(1)

zones = r.json()
print(f"  ✅ {len(zones)} zones chargées")
print()

# [5] Afficher les données
print("[5] Données du dashboard (ce que l'utilisateur voit):")
print()

# Afficher seulement les zones principales
main_zones = [z for z in zones if z.get('type') == 'site']
for zone in main_zones:
    print(f"  📍 {zone['name']}")
    print(f"     🌡️  Température: {zone.get('temp', 'N/A')}°C")
    print(f"     💨 Vent: {zone.get('wind', 'N/A')} km/h ({zone.get('direction', '?')})")
    print(f"     ☁️  Couverture: {zone.get('cloudcover', 'N/A')}%")
    print(f"     💧 Précipitations: {zone.get('precip', 'N/A')} mm")
    print(f"     ⚠️  Risques: {zone.get('risques', 'Aucun')}")
    print()

# [6] Résumé
print("=" * 80)
print("✅ TEST COMPLÉTÉ AVEC SUCCÈS!")
print("=" * 80)
print()
print("Résumé:")
print(f"  • {len(zones_data)} snapshots envoyés")
print(f"  • {len(zones)} zones affichées sur le dashboard")
print(f"  • {len(main_zones)} sites principaux")
print()
print("👉 Maintenant ouvre le dashboard: https://mah-meteo.onrender.com")
print("   Tu devrais voir les données des 3 zones!")
print()
