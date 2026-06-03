#!/usr/bin/env python3
"""Debug: Tester post_to_render directement"""
import os
import requests
import json

# Charger .env
from dotenv import load_dotenv
load_dotenv()

print("[1] Configuration:")
GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS", "false").lower() == "true"
print(f"  GITHUB_ACTIONS={os.getenv('GITHUB_ACTIONS')} -> {GITHUB_ACTIONS}")
print(f"  RENDER_URL={os.getenv('RENDER_URL')}")
print(f"  RENDER_API_TOKEN={os.getenv('RENDER_API_TOKEN', '')[:30]}...")

print("\n[2] Récupération token...")
def get_jwt_token():
    """Reprendre la logique"""
    RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")
    RENDER_API_TOKEN = os.getenv("RENDER_API_TOKEN", "")
    JWT_SECRET = os.getenv("JWT_SECRET", "geodis-secret-key-2024")
    
    try:
        response = requests.get(f"{RENDER_URL}/api/service/token", timeout=5)
        if response.status_code == 200:
            token = response.json().get('token')
            print(f"  ✅ Fetched fresh token: {token[:30]}...")
            return token
    except Exception as e:
        print(f"  ⚠️ Can't fetch fresh token: {e}")
    
    if RENDER_API_TOKEN:
        print(f"  ✅ Using RENDER_API_TOKEN: {RENDER_API_TOKEN[:30]}...")
        return RENDER_API_TOKEN
    
    # Fallback: Generate locally
    try:
        import jwt
        token = jwt.encode(
            {"client_id": 1, "username": "service-meteo"},
            JWT_SECRET,
            algorithm="HS256"
        )
        print(f"  ⚠️ Generated local token: {token[:30]}...")
        return token
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return None

token = get_jwt_token()

if token:
    print("\n[3] Envoi test à Render...")
    payload = {
        "zone_name": "Le Meux 🏣",
        "temperature": 22.0,
        "windspeed": 15.5,
        "wind_direction": "SW",
        "precipitation": 0.8,
        "cloudcover": 45.0,
        "uv_index": 6.0,
        "risques": "Aucun risque majeur",
        "ciel": "Dégagé"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")
    RENDER_API_URL = f"{RENDER_URL}/api/meteo/snapshot/add"
    
    print(f"  URL: {RENDER_API_URL}?client_id=1")
    print(f"  Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{RENDER_API_URL}?client_id=1",
            headers=headers,
            json=payload,
            timeout=10
        )
        print(f"\n  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")
        
        if response.status_code == 200:
            print("\n✅ SUCCESS - Données envoyées!")
        else:
            print(f"\n❌ FAILED - Status {response.status_code}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
else:
    print("\n❌ No token available")
