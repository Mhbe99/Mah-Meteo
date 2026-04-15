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

# Flag circuit-breaker: si SMTP est down, on arrête d'essayer pour ce cycle
_smtp_unreachable = False

# Cache local pour incidents TomTom (30min de TTL)
TRAFIC_CACHE_FILE = "exports/trafic_cache.json"
TRAFIC_CACHE_TTL = 30 * 60  # 30 minutes en secondes


# ============ CACHE MANAGEMENT ============

def load_trafic_cache():
    """
    Charge le cache des incidents TomTom s'il existe et n'est pas expiré.
    Retourne (incidents_list, is_valid) où is_valid=True si cache < 30min.
    """
    try:
        if not os.path.exists(TRAFIC_CACHE_FILE):
            return None, False
        
        with open(TRAFIC_CACHE_FILE, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        
        timestamp = cache_data.get("timestamp", 0)
        age_sec = time.time() - timestamp
        is_valid = age_sec < TRAFIC_CACHE_TTL
        
        incidents = cache_data.get("incidents", [])
        
        if is_valid:
            print(f"[CACHE] ✅ Cache valide ({int(age_sec)}s / {TRAFIC_CACHE_TTL}s)")
        else:
            print(f"[CACHE] ⏰ Cache expiré ({int(age_sec)}s / {TRAFIC_CACHE_TTL}s) - sera utilisé en fallback")
        
        return incidents, is_valid
    except Exception as e:
        print(f"[CACHE] Erreur lecture cache: {e}")
        return None, False


def save_trafic_cache(incidents: list):
    """
    Sauvegarde les incidents TomTom dans le cache local.
    """
    try:
        cache_data = {
            "timestamp": time.time(),
            "incidents": incidents
        }
        os.makedirs(os.path.dirname(TRAFIC_CACHE_FILE), exist_ok=True)
        with open(TRAFIC_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        print(f"[CACHE] 💾 Sauvegarde {len(incidents)} incident(s)")
    except Exception as e:
        print(f"[CACHE] Erreur sauvegarde cache: {e}")


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

    global _smtp_unreachable

    if not sender or not password or not receivers:
        print("[TRAFIC] Credentials email manquants ou RECEIVER_EMAILS vide")
        return

    # Circuit-breaker: si SMTP déjà échoué ce cycle, ne pas retenter
    if _smtp_unreachable:
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

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, receivers, msg.as_string())

        print(f"[TRAFIC] Email alerte envoye pour {incident['route']}")

        # Sauvegarder timestamp cooldown
        state[incident["route"][:50]] = datetime.datetime.now().isoformat()
        os.makedirs("exports", exist_ok=True)
        with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    except OSError as e:
        print(f"[TRAFIC] SMTP injoignable ({e}) — emails desactives pour ce cycle")
        _smtp_unreachable = True
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

    # ============ VÉRIFIER LE CACHE D'ABORD ============
    cached_incidents, cache_valid = load_trafic_cache()
    if cache_valid and cached_incidents is not None:
        # Cache valide (< 30min) — retourner sans appeler TomTom
        retard_max = max([inc["delay_minutes"] for inc in cached_incidents], default=0) if cached_incidents else 0
        return {
            "incidents": cached_incidents,
            "total": len(cached_incidents),
            "retard_max": retard_max,
            "zones_verifiees": 0  # 0 = données en cache
        }

    # ============ CACHE EXPIRÉ OU ABSENT — ESSAYER TOMTOM ============

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

                # Appel TomTom API — Utiliser dict params pour bien encoder l'URL
                url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
                params = {
                    "key": TOMTOM_API_KEY,
                    "bbox": f"{lon_min},{lat_min},{lon_max},{lat_max}",
                    "language": "fr-FR",
                    "timeValidity": "present",
                    "fields": (
                        "{incidents{type,geometry{type,coordinates},"
                        "properties{id,iconCategory,magnitudeOfDelay,"
                        "events{description,code,iconCategory},"
                        "startTime,endTime,from,to,length,delay,"
                        "roadNumbers,timeValidity}}}"
                    )
                }

                r = requests.get(url, params=params, timeout=10)
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
                # Gestion spéciale pour erreur 403 (quota atteint)
                if "403" in str(e):
                    print(f"[TRAFIC] ⚠️ Quota TomTom atteint (Forbidden 403) - ARRÊT (fallback au cache)")
                    # ARRÊTER complètement la boucle pour ne pas épuiser le quota
                    break
                else:
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
        global _smtp_unreachable
        _smtp_unreachable = False  # Reset pour ce cycle
        for inc in incidents_list:
            if inc["severity"] == "high" and not _smtp_unreachable:
                send_email_trafic(inc)

        # Archiver incidents dans JSON historique
        if incidents_list:
            archiver_incidents(incidents_list)

        # Calculer max delay
        retard_max = max((i["delay_minutes"] for i in incidents_list), default=0)

        print(f"[TRAFIC] {len(incidents_list)} incident(s) detecte(s) sur {len(zones)} zone(s)")

        # ============ SAUVEGARDER TOUJOURS EN CACHE (même si vide) ============
        save_trafic_cache(incidents_list)
        
        # Retourner les incidents (peut être vide)
        retard_max = max((i["delay_minutes"] for i in incidents_list), default=0)
        return {
            "incidents": incidents_list,
            "total": len(incidents_list),
            "retard_max": retard_max,
            "zones_verifiees": len(zones)
        }

    except Exception as e:
        print(f"[TRAFIC] Erreur critique: {e}")
        # En case de crash total, essayer le cache
        cached, _ = load_trafic_cache()
        if cached:
            print(f"[FALLBACK] 🆘 Erreur critique - utilisation du cache en dernier recours")
            return {"incidents": cached, "total": len(cached), "retard_max": 0, "zones_verifiees": 0}
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
