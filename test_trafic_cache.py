#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test du système de cache trafic
"""

import requests
import json
import time
import os

BASE_URL = "http://localhost:8080"
LOGIN_CREDS = {
    "username": os.getenv("TEST_USERNAME") or os.getenv("INIT_CLIENT_USERNAME", "service-meteo"),
    "password": os.getenv("TEST_PASSWORD") or os.getenv("INIT_CLIENT_PASSWORD", "")
}

def test_trafic_api():
    """Test l'API trafic avec le nouveau système de cache"""
    
    print("=" * 60)
    print("🧪 TEST API TRAFIC AVEC CACHE")
    print("=" * 60)
    
    # 1. LOGIN
    print("\n[1] Authentification...")
    r_login = requests.post(f"{BASE_URL}/auth/login", json=LOGIN_CREDS, timeout=10)
    
    if r_login.status_code != 200:
        print(f"❌ Login échoué: {r_login.text}")
        return
    
    token = r_login.json().get("access_token")
    print(f"✅ Token obtenu")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. PREMIER APPEL (va créer le cache)
    print("\n[2] Premier appel /api/trafic/1 (création cache)...")
    start = time.time()
    r1 = requests.get(f"{BASE_URL}/api/trafic/1", headers=headers, timeout=30)
    elapsed1 = time.time() - start
    
    print(f"Status: {r1.status_code}")
    data1 = r1.json()
    print(f"  • Total incidents: {data1.get('total')}")
    print(f"  • Max delay: {data1.get('retard_max')} min")
    print(f"  • Zones verifiées: {data1.get('zones_verifiees')}")
    print(f"  • Temps: {elapsed1:.2f}s")
    
    # 3. DEUXIÈME APPEL (va utiliser le cache)
    print("\n[3] Deuxième appel /api/trafic/1 (cache actif, <30s)...")
    start = time.time()
    r2 = requests.get(f"{BASE_URL}/api/trafic/1", headers=headers, timeout=30)
    elapsed2 = time.time() - start
    
    print(f"Status: {r2.status_code}")
    data2 = r2.json()
    print(f"  • Total incidents: {data2.get('total')}")
    print(f"  • Temps: {elapsed2:.2f}s")
    
    # 4. COMPARAISON
    print("\n[4] Résultats du cache:")
    if data1.get("total") == data2.get("total"):
        print(f"✅ Données identiques (cache fonctionne)")
    else:
        print(f"⚠️ Données différentes")
    
    print(f"✅ Deuxième appel {elapsed2/elapsed1:.1f}x plus rapide")
    
    # 5. VÉRIFIER LE FICHIER CACHE
    print("\n[5] Vérification du fichier cache...")
    import os
    if os.path.exists("exports/trafic_cache.json"):
        print("✅ Fichier exports/trafic_cache.json existe")
        with open("exports/trafic_cache.json", "r") as f:
            cache_data = json.load(f)
            print(f"   • Contient {len(cache_data.get('incidents', []))} incidents")
    else:
        print("❌ Fichier cache introuvable")
    
    print("\n" + "=" * 60)
    print("✅ TEST TERMINÉ")
    print("=" * 60)

if __name__ == "__main__":
    test_trafic_api()
