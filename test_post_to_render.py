#!/usr/bin/env python3
"""Test unitaire post_to_render()"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")
RENDER_API_URL = f"{RENDER_URL}/api/meteo/snapshot/add"
RENDER_API_TOKEN = os.getenv("RENDER_API_TOKEN", "")
CLIENT_ID = 1

def get_jwt_token_fresh():
    """Récupère un token frais de Render"""
    try:
        response = requests.get(
            f"{RENDER_URL}/api/service/token",
            timeout=5
        )
        if response.status_code == 200:
            return response.json().get("token")
    except Exception as e:
        print(f"Erreur: {e}")
    return RENDER_API_TOKEN

print("=" * 80)
print("🧪 TEST post_to_render() - VERSION SIMPLE")
print("=" * 80)
print()

# Récupérer token frais
print("[1] Récupération token frais...")
token = get_jwt_token_fresh()
if not token:
    print("❌ Pas de token!")
    exit(1)
print(f"✅ Token: {token[:40]}...")

# Préparer les données
print("\n[2] Préparation des données...")
data = {
    "zone_name": "Le Meux",
    "temperature": 22.3,
    "windspeed": 18.5,
    "wind_direction": "NO",
    "precipitation": 1.2,
    "cloudcover": 45,
    "uv_index": 5,
    "risques": "Vent modéré",
    "ciel": "Nuageux"
}
print(f"✅ Zone: {data['zone_name']}, Temp: {data['temperature']}°C")

# Envoyer les données
print("\n[3] Envoi à Render...")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

url = f"{RENDER_API_URL}?client_id={CLIENT_ID}"
response = requests.post(url, headers=headers, json=data, timeout=10)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("✅ SUCCÈS!")
    print(f"Réponse: {response.json()}")
else:
    print(f"❌ ERREUR: {response.text[:300]}")

print("\n" + "=" * 80)
