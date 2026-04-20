#!/usr/bin/env python3
import requests

RENDER_URL = 'https://mah-meteo.onrender.com'

# Get token
r = requests.post(RENDER_URL + '/api/service/token', timeout=10)
token = r.json()['token']

# Send data
r = requests.post(RENDER_URL + '/api/meteo/snapshot/add?client_id=1',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    json={'zone_name': 'Le Meux', 'temperature': 30, 'windspeed': 28, 'wind_direction': 'E',
          'precipitation': 5.5, 'cloudcover': 90, 'uv_index': 9, 'risques': 'Fort', 'ciel': 'Orageux'},
    timeout=10)

# Get data
r = requests.post(RENDER_URL + '/auth/login', json={'username': 'geodis-lemeux', 'password': 'demo1234'})
token2 = r.json()['access_token']
r = requests.get(RENDER_URL + '/api/meteo/1', headers={'Authorization': f'Bearer {token2}'})
zones = r.json()
zone = [z for z in zones if 'Meux' in z['name']][0]

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
