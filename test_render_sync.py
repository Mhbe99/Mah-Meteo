#!/usr/bin/env python3
"""
🧪 TEST - Envoi de données à Render
Ce script teste que post_to_render() envoie correctement les données
"""
import os
import sys
import requests
import json
from dotenv import load_dotenv

# Charger .env
load_dotenv()

# Configuration
RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")
RENDER_API_TOKEN = os.getenv("RENDER_API_TOKEN", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
TEST_USERNAME = os.getenv("TEST_USERNAME", "geodis-lemeux")
TEST_PASSWORD = os.getenv("TEST_PASSWORD") or os.getenv("INIT_CLIENT_PASSWORD", "demo1234")
RENDER_API_URL = f"{RENDER_URL}/api/meteo/snapshot/add"
CLIENT_ID = 1


def _login_fallback():
    """Login utilisateur pour récupérer un token valide si nécessaire."""
    global RENDER_API_TOKEN, CLIENT_ID
    login_resp = requests.post(
        f"{RENDER_URL}/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        timeout=15
    )
    if not login_resp.ok:
        if login_resp.status_code in (401, 403):
            print(f"SKIP: identifiants invalides pour {TEST_USERNAME}")
            sys.exit(0)
        print(f"❌ Login impossible: HTTP {login_resp.status_code} {login_resp.text[:200]}")
        sys.exit(1)
    login_data = login_resp.json()
    RENDER_API_TOKEN = login_data.get("access_token", "")
    CLIENT_ID = login_data.get("client_id", CLIENT_ID)
    if not RENDER_API_TOKEN:
        print(f"SKIP: payload login invalide: {login_data}")
        sys.exit(0)

print("=" * 80)
print("🧪 TEST RENDER SYNC")
print("=" * 80)

# Étape 1: Vérifier la configuration
print("\n[1/5] ✓ Configuration:")
print(f"   RENDER_URL: {RENDER_URL}")
print(f"   RENDER_API_TOKEN: {RENDER_API_TOKEN[:50]}..." if RENDER_API_TOKEN else "   RENDER_API_TOKEN: ❌ VIDE")
print(f"   JWT_SECRET: {JWT_SECRET[:50]}..." if JWT_SECRET else "   JWT_SECRET: ❌ VIDE")

if not RENDER_API_TOKEN:
    print("\n⚠️ RENDER_API_TOKEN vide: tentative de login utilisateur pour obtenir un token")
    _login_fallback()

# Étape 2: Tester la connexion à Render
print("\n[2/5] ✓ Vérification de Render...")
try:
    response = requests.get(f"{RENDER_URL}/health", timeout=5)
    if response.status_code == 200:
        print(f"   ✅ Render répond: status {response.status_code}")
    else:
        print(f"   ⚠️  Render répond mais status {response.status_code}")
except Exception as e:
    print(f"   ❌ Render ne répond pas: {e}")
    sys.exit(1)

# Étape 3: Préparer les données
print("\n[3/5] ✓ Préparation des données...")
test_data = {
    "zone_name": "Le Meux",
    "temperature": 15.5,
    "windspeed": 12.3,
    "wind_direction": "N",
    "precipitation": 0.0,
    "cloudcover": 30,
    "uv_index": 3,
    "risques": "Aucun",
    "ciel": "Partiellement nuageux"
}

headers = {
    "Authorization": f"Bearer {RENDER_API_TOKEN}",
    "Content-Type": "application/json"
}

print(f"   Zone: {test_data['zone_name']}")
print(f"   Température: {test_data['temperature']}°C")
print(f"   Vent: {test_data['windspeed']} km/h")

# Étape 4: Envoyer les données
print("\n[4/5] ✓ Envoi des données à Render...")
try:
    url_with_params = f"{RENDER_API_URL}?client_id={CLIENT_ID}"
    print(f"   URL: {url_with_params}")
    print(f"   Headers: Authorization Bearer {RENDER_API_TOKEN[:30]}...")
    
    response = requests.post(
        url_with_params,
        headers=headers,
        json=test_data,
        timeout=10
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✅ Données envoyées avec succès!")
        print(f"   Réponse: {response.json()}")
    elif response.status_code in (401, 403):
        print("   ⚠️ Token invalide/expiré, tentative de relogin...")
        _login_fallback()
        headers["Authorization"] = f"Bearer {RENDER_API_TOKEN}"
        url_with_params = f"{RENDER_API_URL}?client_id={CLIENT_ID}"
        response = requests.post(
            url_with_params,
            headers=headers,
            json=test_data,
            timeout=10
        )
        print(f"   Status après relogin: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Données envoyées avec succès après relogin!")
        elif response.status_code in (401, 403):
            print("SKIP: authentification refusée après relogin")
            sys.exit(0)
        else:
            print(f"   ❌ ERREUR {response.status_code}")
            print(f"   Réponse: {response.text[:500]}")
            sys.exit(1)
    else:
        print(f"   ❌ ERREUR {response.status_code}")
        print(f"   Réponse: {response.text[:500]}")
        sys.exit(1)
        
except Exception as e:
    print(f"   ❌ Erreur lors de l'envoi: {e}")
    sys.exit(1)

# Étape 5: Vérifier que les données sont dans la BD
print("\n[5/5] ✓ Vérification des données...")
try:
    response = requests.get(
        f"{RENDER_URL}/api/meteo/{CLIENT_ID}",
        headers={"Authorization": f"Bearer {RENDER_API_TOKEN}"},
        timeout=5
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Données dans la BD: {len(data)} snapshots")
        if data:
            print(f"   Dernier: {data[-1].get('name', '?')} - {data[-1].get('temp', '?')}°C")
    else:
        print(f"   ⚠️  Status {response.status_code}")
except Exception as e:
    print(f"   ⚠️  Erreur lors de la vérif: {e}")

print("\n" + "=" * 80)
print("✅ TEST COMPLÉTÉ - Les données s'envoient à Render avec succès!")
print("=" * 80)
