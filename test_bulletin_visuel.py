#!/usr/bin/env python3
"""
Test visuel : envoie un bulletin email avec données fictives réalistes.
Simule un créneau 10h30 avec alertes actives sur une zone.
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# Charger .env avant l'import du module
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    print("[.env] Chargé")
except ImportError:
    print("[.env] python-dotenv absent — variables .env non chargées")

sys.path.insert(0, str(Path(__file__).parent))

from meteo_saas.backend.email_alerts import send_bulletin_email


# ── Données zones fictives (simule SQLAlchemy Zone) ─────────────────────────
class FakeZone:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


zones = [
    FakeZone(
        name="GEODIS Valenton",
        type="site",
        temperature=3.2,
        windspeed=52.0,
        wind_direction="NO",
        precipitation=0.0,
        uv_index=1.2,
        ciel="🌥",
        risques="🟠 Vent fort | 🟠 Gel",
    ),
    FakeZone(
        name="GEODIS Gonesse",
        type="site",
        temperature=4.1,
        windspeed=38.0,
        wind_direction="N",
        precipitation=1.5,
        uv_index=0.8,
        ciel="🌧",
        risques="🟠 Pluie modérée",
    ),
    FakeZone(
        name="A86 — Créteil",
        type="voisin",
        temperature=3.8,
        windspeed=55.0,
        wind_direction="NO",
        precipitation=0.0,
        uv_index=1.0,
        ciel="🌥",
        risques="🔴 Vent fort",
    ),
    FakeZone(
        name="A1 — Roissy",
        type="voisin",
        temperature=2.5,
        windspeed=22.0,
        wind_direction="O",
        precipitation=3.2,
        uv_index=0.5,
        ciel="🌧",
        risques="✅ RAS",
    ),
    FakeZone(
        name="GEODIS Bonneuil",
        type="site",
        temperature=4.8,
        windspeed=18.0,
        wind_direction="S",
        precipitation=0.0,
        uv_index=2.1,
        ciel="⛅",
        risques="✅ RAS",
    ),
]

# ── Incidents trafic fictifs ─────────────────────────────────────────────────
incidents = [
    {
        "route": "A86 Créteil → Valenton",
        "description": "Accident — voie de droite obstruée",
        "severity": "major",
        "delay_minutes": 42,
    },
    {
        "route": "A1 CDG — Porte de la Chapelle",
        "description": "Travaux de nuit prolongés",
        "severity": "minor",
        "delay_minutes": 18,
    },
    {
        "route": "N2 Gonesse — Le Bourget",
        "description": "Bouchon habituel",
        "severity": "minor",
        "delay_minutes": 9,
    },
]

# ── Envoi ────────────────────────────────────────────────────────────────────
DEST = os.getenv("RECEIVER_EMAILS", "mahmeteo@gmail.com").split(",")[0].strip()

print(f"\n[TEST] Envoi bulletin visuel → {DEST}")
print(f"[TEST] Zones : {len(zones)} | Incidents : {len(incidents)}")
print("[TEST] Créneau simulé : 10h30\n")

ok = send_bulletin_email(
    to_email=DEST,
    company_name="GEODIS Ile-de-France",
    zones=zones,
    incidents=incidents,
    creneau="10h30",
)

if ok:
    print(f"\n✅ Bulletin envoyé à {DEST} — vérifiez votre boîte.")
else:
    print("\n❌ Échec de l'envoi — vérifiez les variables .env (GMAIL_PASSWORD, SENDER_EMAIL...)")
