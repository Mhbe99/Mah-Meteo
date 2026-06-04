import os
import requests

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")
if not TOMTOM_API_KEY:
    raise SystemExit("TOMTOM_API_KEY manquante")
zone_lat, zone_lon = 49.108829, 2.5003929999999997

lat_min = zone_lat - 0.27
lat_max = zone_lat + 0.27
lon_min = zone_lon - 0.39
lon_max = zone_lon + 0.39

print('=== TEST 1: Sans categoryFilter ===')
url = 'https://api.tomtom.com/traffic/services/5/incidentDetails'
params = {
    'key': TOMTOM_API_KEY,
    'bbox': f'{lon_min},{lat_min},{lon_max},{lat_max}',
    'language': 'fr-FR',
    'timeValidity': 'present'
}
try:
    r = requests.get(url, params=params, timeout=5)
    print(f'Status: {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        print(f'SUCCESS! Incidents: {len(data.get("incidents", []))}')
    else:
        print(f'Error: {r.text[:150]}')
except Exception as e:
    print(f'Error: {e}')
