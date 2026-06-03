#!/usr/bin/env python3
"""Test: Lancer meteo_open.py manuellement et vérifier les données sur Render"""
import requests
import time

RENDER_URL = 'https://mah-meteo.onrender.com'

print()
print('╔' + '═'*62 + '╗')
print('║  TEST: DONNÉES ENVOYÉES MANUELLEMENT À RENDER             ║')
print('╚' + '═'*62 + '╝')
print()

# Login
print('[1] Authentification...')
r = requests.post(RENDER_URL + '/auth/login', json={'username': 'geodis-lemeux', 'password': 'demo1234'})
if r.status_code != 200:
    print(f'❌ Login failed: {r.status_code}')
    exit(1)
token = r.json()['access_token']
print('✅ Authentification OK')

# Get meteo data
print('[2] Récupération données...')
r = requests.get(RENDER_URL + '/api/meteo/1', headers={'Authorization': f'Bearer {token}'})
zones = r.json()
print(f'✅ {len(zones)} zones chargées')

# Show main sites with data
print()
print('DONNÉES AFFICHÉES SUR LE DASHBOARD:')
print('─' * 62)
has_data = False
for zone in zones:
    if zone['type'] == 'site':
        if zone['temp'] is not None:
            has_data = True
            precip = zone.get('precipitation', '?')
            cloud = zone.get('cloudcover', '?')
            uv = zone.get('uv_index', '?')
            print(f"  {zone['name']:18s} | Temp: {zone['temp']:5.1f}C | Vent: {zone['wind']:5.1f}km/h")
            print(f"  {' '*18} | Precip: {precip} mm | Cloud: {cloud}% | UV: {uv}")
            print()

if has_data:
    print('✅ LE PROBLÈME EST RÉSOLU!')
    print('   Les données s\'affichent normalement sur le dashboard')
    print()
    print('📅 AVANT LE 1ER AVRIL:')
    print('   • Tu peux lancer meteo_open.py manuellement')
    print('   • Ou créer une boucle qui le lance toutes les 22 min')
    print()
    print('📅 À PARTIR DU 1ER AVRIL:')
    print('   • GitHub Actions lancera meteo_open.py')
    print('   • Automatiquement toutes les 22 minutes')
    print('   • Les données s\'enverront toutes seules à Render')
else:
    print('⚠️  Pas de données affichées encore')

print()
