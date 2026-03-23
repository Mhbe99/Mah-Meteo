# -*- coding: utf-8 -*-
"""
trafic.py — Intégration API TomTom Traffic avec incidents en temps réel
Surveillance par zone individuelle (rayon 30km) avec archivage et alertes email
"""

import os
import json
import time
import smtplib
import datetime
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")


def get_icon(category: int) -> str:
    """
    Retourne l'emoji correspondant au type d'incident TomTom.
    Les emojis sont utilisés pour l'affichage visuel des incidents.
    
    Args:
        category : code iconCategory de TomTom API
    
    Returns:
        Emoji représentant le type d'incident
    """
    icons = {
        1:  "[CRASH]",      # Accident
        2:  "[FOG]",        # Brouillard
        3:  "[ALERT]",      # Conditions dangereuses
        4:  "[RAIN]",       # Pluie sur chaussée
        5:  "[ICE]",        # Verglas
        6:  "[TRAFFIC]",    # Bouchon
        7:  "[CONSTRUCTION]",  # Voie fermée
        8:  "[CLOSED]",     # Route fermée
        9:  "[WORK]",       # Travaux
        10: "[WIND]",       # Vent fort
        11: "[FLOOD]",      # Inondation
        13: "[BREAKDOWN]",  # Véhicule en panne
        14: "[OTHER]",      # Autre
    }
    return icons.get(category, "[OTHER]")


def send_email_trafic(incident: dict):
    """
    Envoie un email d'alerte pour un incident trafic grave (HIGH severity).
    Implémente un cooldown de 1h par route pour éviter le spam.
    
    Args:
        incident : dict incident avec clés route, description, severity, delay_minutes, zone_source
    
    Returns:
        None (logs l'envoi ou l'erreur)
    """
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("GMAIL_PASSWORD")
    receivers_str = os.getenv("RECEIVER_EMAILS", "")
    receivers = [r.strip() for r in receivers_str.split(",") if r.strip()]

    if not sender or not password or not receivers:
        print("[TRAFIC] Credentials email manquants ou RECEIVER_EMAILS vide")
        return

    # Gestion cooldown 1h par route
    COOLDOWN_FILE = "exports/last_trafic_alerts.json"
    try:
        state = {}
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

        key = incident["route"][:50]
        if key in state:
            last_time = datetime.datetime.fromisoformat(state[key])
            delta_sec = (datetime.datetime.now() - last_time).total_seconds()
            if delta_sec < 3600:  # Cooldown 1h
                print(f"[TRAFIC] Cooldown actif pour {key} ({int(delta_sec)}s/3600s)")
                return
    except Exception:
        state = {}

    # Construire l'email
    subject = f"[MAH METEO] Alerte trafic : {incident['route']}"
    body = (
        f"Incident signale dans votre zone de surveillance\n\n"
        f"Route      : {incident['route']}\n"
        f"Type       : {incident['icon']} {incident['description']}\n"
        f"Severite   : {incident['severity'].upper()}\n"
        f"Retard     : +{incident['delay_minutes']} min\n"
        f"Zone       : {incident.get('zone_source', 'N/A')}\n"
        f"GPS        : {incident['lat']}, {incident['lon']}\n\n"
        f"Detecte le {datetime.datetime.now().strftime('%d/%m/%Y a %H:%M')}\n\n"
        f"-- Mah Meteo | Surveillance automatique --"
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = ", ".join(receivers)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receivers, msg.as_string())

        print(f"[TRAFIC] Email alerte envoye pour {incident['route']}")

        # Sauvegarder timestamp cooldown
        state[incident["route"][:50]] = datetime.datetime.now().isoformat()
        os.makedirs("exports", exist_ok=True)
        with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[TRAFIC] Erreur envoi email : {e}")


def archiver_incidents(incidents: list):
    """
    Archive les incidents trafic dans exports/trafic_historique.json.
    Conserve un maximum de 500 entrées (rotation FIFO).
    
    Args:
        incidents : liste d'incidents à archiver
    
    Returns:
        None (logs l'archivage ou l'erreur)
    """
    ARCHIVE_FILE = "exports/trafic_historique.json"
    try:
        historique = []
        if os.path.exists(ARCHIVE_FILE):
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                historique = json.load(f)

        now = datetime.datetime.now().isoformat()
        for inc in incidents:
            historique.append({
                "timestamp": now,
                "route": inc["route"],
                "description": inc["description"],
                "severity": inc["severity"],
                "delay_minutes": inc["delay_minutes"],
                "icon": inc["icon"],
                "zone_source": inc.get("zone_source", ""),
                "lat": inc["lat"],
                "lon": inc["lon"]
            })

        # Garder max 500 entrées (histor rotation FIFO)
        if len(historique) > 500:
            historique = historique[-500:]

        os.makedirs("exports", exist_ok=True)
        with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(historique, f, ensure_ascii=False, indent=2)

        print(f"[TRAFIC] {len(incidents)} incident(s) archive(s) dans historique (+{len(historique)} total)")

    except Exception as e:
        print(f"[TRAFIC] Erreur archivage incidents : {e}")


def get_incidents(zones: list, test_mode: bool = False) -> dict:
    """
    Récupère les incidents trafic TomTom pour chaque zone individuellement.
    Boucle sur chaque zone avec rayon 30km, déduplique les incidents,
    puis envoie alertes email pour HIGH severity et archive dans JSON.
    
    Args:
        zones : liste de dicts {"name", "lat", "lon", "type"}
        test_mode : True retourne 3 incidents fictifs pour démo
    
    Returns:
        dict avec clés:
        - incidents: liste d'incidents triés par sévérité
        - total: nombre total d'incidents
        - retard_max: délai maximum en minutes
        - zones_verifiees: nombre de zones scannées
        
        ou dict {'incidents': [], 'total': 0, 'retard_max': 0, 'zones_verifiees': 0} si erreur
    """
    if not TOMTOM_API_KEY:
        print("[WARNING] TOMTOM_API_KEY manquante dans .env")
        return {"incidents": [], "total": 0, "retard_max": 0, "zones_verifiees": 0}

    # MODE TEST — Retourne des incidents fictifs pour démo
    if test_mode:
        test_incidents = [
            {
                "route": "A1 -- Le Meux -> Clairoix",
                "description": "[TEST] Accident signale",
                "severity": "high",
                "delay_minutes": 45,
                "icon": "[CRASH]",
                "lat": 49.378,
                "lon": 2.750,
                "zone_source": "Le Meux"
            },
            {
                "route": "RN 31 -- Compiegne -> Beauvais",
                "description": "[TEST] Travaux en cours",
                "severity": "med",
                "delay_minutes": 20,
                "icon": "[WORK]",
                "lat": 49.419,
                "lon": 2.832,
                "zone_source": "Clairoix"
            },
            {
                "route": "D1000 -- Creil -> Senlis",
                "description": "[TEST] Congestion reguliere",
                "severity": "low",
                "delay_minutes": 10,
                "icon": "[TRAFFIC]",
                "lat": 49.256,
                "lon": 2.483,
                "zone_source": "Creil"
            }
        ]
        print("[TRAFIC] MODE TEST: 3 incident(s) fictifs retournes")
        return {
            "incidents": test_incidents,
            "total": 3,
            "retard_max": 45,
            "zones_verifiees": 3
        }

    # MODE RÉEL — Boucle sur chaque zone avec rayon 30km
    tous_incidents = {}  # dict pour déduplication par ID TomTom

    if not zones:
        return {"incidents": [], "total": 0, "retard_max": 0, "zones_verifiees": 0}

    try:
        for zone in zones:
            try:
                # Délai anti-throttling (0.3s entre appels API)
                time.sleep(0.3)

                zone_name = zone.get("name", "Zone inconnu")
                zone_lat = zone.get("lat", 0)
                zone_lon = zone.get("lon", 0)

                # Bbox 30km autour de la zone (±0.27° lat, ±0.39° lon)
                lat_min = zone_lat - 0.27
                lat_max = zone_lat + 0.27
                lon_min = zone_lon - 0.39
                lon_max = zone_lon + 0.39

                # Appel TomTom API
                url = (
                    f"https://api.tomtom.com/traffic/services/5/incidentDetails"
                    f"?key={TOMTOM_API_KEY}"
                    f"&bbox={lon_min},{lat_min},{lon_max},{lat_max}"
                    f"&fields={{incidents{{type,geometry{{coordinates}},"
                    f"properties{{id,iconCategory,magnitudeOfDelay,"
                    f"events{{description,code}},startTime,endTime,"
                    f"from,to,length,delay,roadNumbers,timeValidity}}}}}}"
                    f"&language=fr-FR"
                    f"&categoryFilter=0,1,2,3,4,5,6,7,8,9,10,11,13,14"
                    f"&timeValidityFilter=present"
                )

                r = requests.get(url, timeout=10)
                r.raise_for_status()
                data = r.json()

                # Parser incidents de cette zone
                for item in data.get("incidents", []):
                    props = item.get("properties", {})
                    incident_id = props.get("id", "")

                    # Dédupliquer par ID TomTom
                    if not incident_id or incident_id in tous_incidents:
                        continue

                    # Extraire coordonnées géométriques
                    geometry = item.get("geometry", {})
                    coords = geometry.get("coordinates", [[zone_lon, zone_lat]])
                    if isinstance(coords[0], list):
                        lon_inc = coords[0][0]
                        lat_inc = coords[0][1]
                    else:
                        lon_inc = coords[0]
                        lat_inc = coords[1]

                    # Mapper magnitudeOfDelay TomTom (0-4) vers sévérité
                    mag = props.get("magnitudeOfDelay", 0)
                    if mag <= 1:
                        severity = "low"
                    elif mag == 2:
                        severity = "med"
                    else:
                        severity = "high"

                    # Convertir délai de secondes en minutes
                    delay_sec = props.get("delay", 0) or 0
                    delay_min = round(delay_sec / 60)

                    # Description depuis premier événement
                    events = props.get("events", [])
                    description = events[0].get("description", "Incident signale") if events else "Incident signale"

                    # Construire nom de route
                    road_numbers = props.get("roadNumbers", [])
                    from_loc = props.get("from", "")
                    to_loc = props.get("to", "")
                    if road_numbers:
                        route = f"{road_numbers[0]} — {from_loc} → {to_loc}"
                    else:
                        route = f"{from_loc} → {to_loc}" if from_loc else "Route locale"

                    # Icône selon catégorie TomTom
                    category = props.get("iconCategory", 14)
                    icon = get_icon(category)

                    # Ajouter incident formaté
                    tous_incidents[incident_id] = {
                        "route": route,
                        "description": description,
                        "severity": severity,
                        "delay_minutes": delay_min,
                        "icon": icon,
                        "lat": lat_inc,
                        "lon": lon_inc,
                        "zone_source": zone_name
                    }

            except requests.RequestException as e:
                print(f"[TRAFIC] Erreur API zone {zone_name}: {e}")
                continue
            except Exception as e:
                print(f"[TRAFIC] Erreur parsing zone {zone_name}: {e}")
                continue

        # Convertir dict en liste triée par sévérité (high → med → low)
        order = {"high": 0, "med": 1, "low": 2}
        incidents_list = sorted(
            tous_incidents.values(),
            key=lambda x: order.get(x["severity"], 3)
        )

        # Envoyer emails pour incidents HIGH severity
        for inc in incidents_list:
            if inc["severity"] == "high":
                send_email_trafic(inc)

        # Archiver incidents dans JSON historique
        if incidents_list:
            archiver_incidents(incidents_list)

        # Calculer max delay
        retard_max = max((i["delay_minutes"] for i in incidents_list), default=0)

        print(f"[TRAFIC] {len(incidents_list)} incident(s) detecte(s) sur {len(zones)} zone(s)")

        return {
            "incidents": incidents_list,
            "total": len(incidents_list),
            "retard_max": retard_max,
            "zones_verifiees": len(zones)
        }

    except Exception as e:
        print(f"[TRAFIC] Erreur critique: {e}")
        return {"incidents": [], "total": 0, "retard_max": 0, "zones_verifiees": 0}


def get_alerte_combinee(incidents: list, risques_actifs: list) -> dict | None:
    """
    Génère une alerte combinée météo + trafic si conditions réunies.
    
    Args:
        incidents : liste d'incidents trafic
        risques_actifs : liste de risques météo détectés
    
    Returns:
        dict avec 'niveau' et 'message' si danger détecté, None sinon
    """
    incidents_high = [i for i in incidents if i["severity"] == "high"]
    if not incidents_high or not risques_actifs:
        return None

    risques_str = " | ".join(risques_actifs)
    incident = incidents_high[0]
    return {
        "niveau": "danger",
        "route": incident["route"],
        "message": (
            f"Incident majeur sur {incident['route']} "
            f"(+{incident['delay_minutes']} min) "
            f"combiné avec : {risques_str}. "
            f"Retard total estimé +{incident['delay_minutes'] + 15} min."
        )
    }
