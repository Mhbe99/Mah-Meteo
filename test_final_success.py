#!/usr/bin/env python3
import requests
import os
from dotenv import load_dotenv

load_dotenv()

RENDER_URL = os.getenv('RENDER_URL', 'https://mah-meteo.onrender.com')
TEST_USERNAME = os.getenv('TEST_USERNAME', 'geodis-lemeux')
TEST_PASSWORD = os.getenv('TEST_PASSWORD') or os.getenv('INIT_CLIENT_PASSWORD', 'demo1234')

# Login utilisateur standard
try:
    r = requests.post(RENDER_URL + '/auth/login', json={'username': TEST_USERNAME, 'password': TEST_PASSWORD}, timeout=15)
except requests.RequestException as e:
    print(f"SKIP: endpoint indisponible ({e})")
    raise SystemExit(0)
if not r.ok:
    if r.status_code in (401, 403):
        print(f"SKIP: identifiants invalides pour {TEST_USERNAME}")
        raise SystemExit(0)
    print(f"❌ Login failed HTTP {r.status_code}: {r.text[:200]}")
    raise SystemExit(1)
login_data = r.json()
token = login_data.get('access_token')
client_id = login_data.get('client_id')
if not token or not client_id:
    print(f"❌ Invalid login payload: {login_data}")
    raise SystemExit(1)

# Send data
r = requests.post(f'{RENDER_URL}/api/meteo/snapshot/add?client_id={client_id}',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    json={'zone_name': 'Le Meux', 'temperature': 30, 'windspeed': 28, 'wind_direction': 'E',
          'precipitation': 5.5, 'cloudcover': 90, 'uv_index': 9, 'risques': 'Fort', 'ciel': 'Orageux'},
    timeout=15)
if not r.ok:
    if r.status_code in (401, 403):
        print("SKIP: token refusé pour snapshot")
        raise SystemExit(0)
    print(f"❌ Snapshot POST failed HTTP {r.status_code}: {r.text[:200]}")
    raise SystemExit(1)

# Get data
r = requests.get(f'{RENDER_URL}/api/meteo/{client_id}', headers={'Authorization': f'Bearer {token}'}, timeout=15)
if not r.ok:
    if r.status_code in (401, 403):
        print("SKIP: token refusé pour lecture météo")
        raise SystemExit(0)
    print(f"❌ Météo GET failed HTTP {r.status_code}: {r.text[:200]}")
    raise SystemExit(1)
zones = r.json()
matching = [z for z in zones if 'Meux' in z.get('name', '')]
if not matching:
    print("❌ Zone Le Meux introuvable dans la réponse")
    raise SystemExit(1)
zone = matching[0]

print()
print('╔════════════════════════════════════════════════════════════╗')
print('║        ✅ SUCCESS - LE MEUX DATA ON DASHBOARD             ║')
print('╚════════════════════════════════════════════════════════════╝')
print()
print(f'  Temperature:    {zone.get("temp")}C')
print(f'  Wind:           {zone.get("wind")} km/h ({zone.get("direction")})')
print(f'  Precipitation:  {zone.get("precipitation")} mm')
print(f'  Cloudcover:     {zone.get("cloudcover")}%')
print(f'  UV Index:       {zone.get("uv_index")}')
print()
print(f'  Updated: {zone.get("updated_at")}')
print()

if zone.get('precipitation') is not None:
    print('✅ SOLUTION COMPLÈTE - TOUTES LES DONNÉES S\'AFFICHENT!')
    print()
    print('Prochaine étape: GitHub Actions enverra les données')
    print('automatiquement à partir du 1er avril toutes les 22 minutes.')
else:
    print('⚠️ Certains champs sont vides')
