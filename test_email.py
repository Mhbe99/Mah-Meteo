# -*- coding: utf-8 -*-
"""
test_email.py — Test d'envoi d'email d'alerte
"""
import os
import sys
from dotenv import load_dotenv

# Charger le .env
load_dotenv()

# Ajouter le chemin pour importer le module
sys.path.insert(0, os.path.dirname(__file__))

from meteo_saas.backend.email_alerts import (
    _send_email, send_meteo_alert, send_trafic_alert, send_combined_alert,
    SMTP_USER, SMTP_FROM, ALERT_ENABLED, RECEIVER_EMAILS
)

print("=" * 50)
print("TEST EMAIL — Mah Météo")
print("=" * 50)
print(f"SMTP_USER     : {SMTP_USER or '(non configuré)'}")
print(f"SMTP_FROM     : {SMTP_FROM or '(non configuré)'}")
print(f"RECEIVERS     : {RECEIVER_EMAILS or '(non configuré)'}")
print(f"ALERT_ENABLED : {ALERT_ENABLED}")
print()

# Déterminer le destinataire
to_email = RECEIVER_EMAILS.split(",")[0].strip() if RECEIVER_EMAILS else SMTP_USER
if not to_email:
    print("ERREUR : Aucun email configuré. Vérifiez .env (SENDER_EMAIL, RECEIVER_EMAILS)")
    sys.exit(1)

print(f"Envoi test vers : {to_email}")
print()

# Test 1 : Alerte météo
print("[1/3] Envoi alerte météo...")
send_meteo_alert(to_email, "GEODIS — Le Meux", [
    {"zone": "Beauvais", "type": "Vent fort", "valeur": "55 km/h", "message": "Rafales dépassant le seuil de 50 km/h"},
    {"zone": "Compiègne", "type": "Pluie modérée", "valeur": "4.5 mm/h", "message": "Risque d'aquaplaning sur A1"},
])

# Test 2 : Alerte trafic
print("[2/3] Envoi alerte trafic...")
send_trafic_alert(to_email, "GEODIS — Le Meux", [
    {"route": "A1 — Compiègne → Paris", "description": "Accident — voie bloquée", "severity": "high", "delay_minutes": 25},
    {"route": "D200 — Le Meux → Pont-Ste-Maxence", "description": "Route fermée — inondation", "severity": "high", "delay_minutes": 0},
])

# Test 3 : Alerte combinée
print("[3/3] Envoi alerte combinée...")
send_combined_alert(to_email, "GEODIS — Le Meux",
    "Attention : pluie modérée prévue à Compiègne + accident A1 = risque de retard important sur les tournées nord. Prévoir 20-30 min supplémentaires."
)

print()
print("Terminé. Vérifie ta boîte mail.")
