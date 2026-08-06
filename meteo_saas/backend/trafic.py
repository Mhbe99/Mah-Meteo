# -*- coding: utf-8 -*-
"""
trafic.py — Intégration API TomTom Traffic avec incidents en temps réel
Surveillance par zone individuelle (rayon 30km) avec archivage et alertes email
"""

import os
import json
import time
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

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


def send_email_trafic_batch(incidents: list, client_id: int | None = None):
    """
    Envoie UNE SEULE notification push récapitulative (accidents, bouchons, travaux, etc.).
    Cooldown global de 1h stocké en base PostgreSQL (survit aux redémarrages Render).
    Filtre : seulement les incidents HIGH et MED — les LOW sont exclus.
    """
    if not incidents:
        print("[TRAFIC] Aucun incident à notifier")
        return

    if client_id is None:
        print("[TRAFIC] client_id manquant — push non envoyé")
        return

    # Tous les niveaux inclus (HIGH, MED, LOW/bouchons) — les bouchons impactent les tournées GEODIS
    # La bbox est déjà limitée à 50km des sites, pas de risque de spam Paris/IDF
    order_sev = {"high": 0, "med": 1, "low": 2}
    incidents = sorted(incidents, key=lambda x: order_sev.get(x.get("severity"), 3))

    # --- Cooldown persistant via PostgreSQL (survit aux redémarrages Render) ---
    COOLDOWN_SECONDS = 3600  # 1 heure
    try:
        from meteo_saas.backend.database import SessionLocal, AlerteLog
        from sqlalchemy import desc
        db = SessionLocal()
        try:
            last_entry = (
                db.query(AlerteLog)
                .filter(AlerteLog.type_alerte == "trafic_batch_email")
                .order_by(desc(AlerteLog.timestamp))
                .first()
            )
            if last_entry:
                delta_sec = (datetime.datetime.utcnow() - last_entry.timestamp).total_seconds()
                if delta_sec < COOLDOWN_SECONDS:
                    print(f"[TRAFIC] Cooldown push actif ({int(delta_sec)}s/{COOLDOWN_SECONDS}s) — push ignoré")
                    return
        finally:
            db.close()
    except Exception as e:
        print(f"[TRAFIC] Cooldown DB indisponible ({e}), vérification fichier fallback")
        # Fallback : fichier local si DB inaccessible
        COOLDOWN_FILE = "exports/last_trafic_alerts.json"
        try:
            state = {}
            if os.path.exists(COOLDOWN_FILE):
                with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
            last_batch = state.get("_last_batch")
            if last_batch:
                delta_sec = (datetime.datetime.now() - datetime.datetime.fromisoformat(last_batch)).total_seconds()
                if delta_sec < COOLDOWN_SECONDS:
                    print(f"[TRAFIC] Cooldown fichier actif ({int(delta_sec)}s/{COOLDOWN_SECONDS}s)")
                    return
        except Exception:
            pass

    total = len(incidents)
    high_count = sum(1 for i in incidents if i["severity"] == "high")
    retard_max = max((i["delay_minutes"] for i in incidents), default=0)

    titre = f"{high_count} incident(s) sévère(s) trafic" if high_count else f"{total} incident(s) trafic"
    corps = f"{total} incident(s) signalé(s) — retard max +{retard_max} min"

    try:
        from meteo_saas.backend.email_alerts import envoyer_push_notification
        from meteo_saas.backend.database import SessionLocal
        db_push = SessionLocal()
        nb_push = envoyer_push_notification(
            db_session=db_push,
            client_id=client_id,
            titre=titre,
            corps=corps,
            type_alerte="trafic",
            url="/?tab=2"
        )
        db_push.close()
    except Exception as e:
        print(f"[TRAFIC] Erreur envoi push: {e}")
        return

    envoye = bool(nb_push)

    # Filet de secours : si le push échoue totalement, on retombe sur l'email.
    if not envoye:
        print("[TRAFIC] ❌ Push trafic non envoyé — fallback email")
        try:
            from meteo_saas.backend.email_alerts import _envoyer_email_secours
            lignes = [
                f"{i.get('route','?')} — {i.get('description','')} "
                f"({i.get('severity','?')}, +{i.get('delay_minutes') or 0} min)"
                for i in incidents[:20]
            ]
            _envoyer_email_secours(
                subject=f"{titre} (secours)",
                intro=f"{total} incident(s) trafic signalé(s) — push indisponible, notification de secours.",
                lignes=lignes,
                to_email="",
            )
            envoye = True
        except Exception as e:
            print(f"[TRAFIC] Erreur fallback email: {e}")

    if not envoye:
        return

    # Si on arrive ici, le push (ou le secours email) a été envoyé — enregistrer le cooldown
    try:
        from meteo_saas.backend.database import SessionLocal, AlerteLog
        db = SessionLocal()
        try:
            entry = AlerteLog(
                client_id=client_id,
                zone_name="_system",
                type_alerte="trafic_batch_email",
                valeur=str(total),
                message=f"{total} incidents notifiés ({high_count} sévères)"
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()
    except Exception as e_db:
        # Fallback fichier si DB inaccessible
        print(f"[TRAFIC] Cooldown DB sauvegarde échouée ({e_db}), fallback fichier")
        try:
            os.makedirs("exports", exist_ok=True)
            with open("exports/last_trafic_alerts.json", "w", encoding="utf-8") as f:
                json.dump({"_last_batch": datetime.datetime.now().isoformat()}, f)
        except Exception:
            pass


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


def get_incidents(zones: list, test_mode: bool = False, client_id: int | None = None) -> dict:
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
    global _smtp_unreachable
    
    if not TOMTOM_API_KEY:
        print("[WARNING] TOMTOM_API_KEY manquante dans .env")
        return {"incidents": [], "total": 0, "retard_max": 0, "zones_verifiees": 0}

    # ============ VÉRIFIER LE CACHE D'ABORD ============
    cached_incidents, cache_valid = load_trafic_cache()
    if cache_valid and cached_incidents is not None:
        # Cache valide (< 30min) — utiliser les données
        # MAIS: appeler send_email_trafic_batch() avec son propre cooldown 1h
        # (le cache n'empêche PAS le push, juste l'API TomTom)
        _smtp_unreachable = False
        if cached_incidents and not _smtp_unreachable:
            send_email_trafic_batch(cached_incidents, client_id=client_id)
        
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

    # MODE RÉEL — UN SEUL appel TomTom avec bbox englobante (toutes les zones)
    tous_incidents = {}  # dict pour déduplication par ID TomTom

    if not zones:
        return {"incidents": [], "total": 0, "retard_max": 0, "zones_verifiees": 0}

    try:
        # Bbox calculée sur les SITES uniquement (jamais sur les voisins qui peuvent être très loin)
        sites = [z for z in zones if z.get("type") == "site"]
        if not sites:
            sites = zones  # fallback si pas de type défini

        site_lats = [z["lat"] for z in sites]
        site_lons = [z["lon"] for z in sites]

        # Centroïde des sites + marge fixe de 0.40° (~44km) — jamais plus
        # 1° lat ≈ 111km, 1° lon ≈ 73km à lat 49°
        MARGE_LAT = 0.40   # ~44km
        MARGE_LON = 0.55   # ~40km à lat 49°
        lat_centre = (min(site_lats) + max(site_lats)) / 2
        lon_centre = (min(site_lons) + max(site_lons)) / 2
        lat_span = (max(site_lats) - min(site_lats)) / 2 + MARGE_LAT
        lon_span = (max(site_lons) - min(site_lons)) / 2 + MARGE_LON

        lat_min = lat_centre - lat_span
        lat_max = lat_centre + lat_span
        lon_min = lon_centre - lon_span
        lon_max = lon_centre + lon_span

        area_km2 = (lat_max - lat_min) * 111 * (lon_max - lon_min) * 73
        bbox_str = f"{lon_min},{lat_min},{lon_max},{lat_max}"
        print(f"[TRAFIC] Bbox sites ({len(sites)} sites): {bbox_str} (~{int(area_km2)}km²)")

        # UN SEUL appel TomTom API
        url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
        params = {
            "key": TOMTOM_API_KEY,
            "bbox": bbox_str,
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

        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        # Parser tous les incidents
        for item in data.get("incidents", []):
            props = item.get("properties", {})
            incident_id = props.get("id", "")

            if not incident_id or incident_id in tous_incidents:
                continue

            # Extraire coordonnées géométriques
            geometry = item.get("geometry", {})
            coords = geometry.get("coordinates", [[0, 0]])
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

            # Trouver la zone la plus proche
            best_zone = "Zone inconnue"
            best_dist = float("inf")
            for z in zones:
                d = (z["lat"] - lat_inc) ** 2 + (z["lon"] - lon_inc) ** 2
                if d < best_dist:
                    best_dist = d
                    best_zone = z.get("name", "Zone inconnue")

            tous_incidents[incident_id] = {
                "route": route,
                "description": description,
                "severity": severity,
                "delay_minutes": delay_min,
                "icon": icon,
                "lat": lat_inc,
                "lon": lon_inc,
                "zone_source": best_zone
            }

        # Post-filtre: exclure tout incident à plus de 50km d'un site GEODIS
        # (élimine les incidents qui passent la bbox mais sont hors zone)
        MAX_DIST_KM = 50.0
        def dist_km(lat1, lon1, lat2, lon2):
            dlat = (lat2 - lat1) * 111
            dlon = (lon2 - lon1) * 73
            return (dlat**2 + dlon**2) ** 0.5

        incidents_filtres = {}
        for inc_id, inc in tous_incidents.items():
            proche = any(
                dist_km(s["lat"], s["lon"], inc["lat"], inc["lon"]) <= MAX_DIST_KM
                for s in sites
            )
            if proche:
                incidents_filtres[inc_id] = inc
            
        nb_exclus = len(tous_incidents) - len(incidents_filtres)
        if nb_exclus > 0:
            print(f"[TRAFIC] {nb_exclus} incident(s) hors zone exclu(s) (>50km des sites)")
        tous_incidents = incidents_filtres

        # Convertir dict en liste triée par sévérité (high → med → low)
        order = {"high": 0, "med": 1, "low": 2}
        incidents_list = sorted(
            tous_incidents.values(),
            key=lambda x: order.get(x["severity"], 3)
        )

        # Envoyer UNE notification push synthèse avec TOUS les incidents
        _smtp_unreachable = False  # Reset pour ce cycle
        if incidents_list and not _smtp_unreachable:
            send_email_trafic_batch(incidents_list, client_id=client_id)

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
        "delay_minutes": incident["delay_minutes"],
        "risques_meteo": risques_str,
        "message": (
            f"Incident majeur sur {incident['route']} "
            f"(+{incident['delay_minutes']} min) "
            f"combiné avec : {risques_str}. "
            f"Retard total estimé +{incident['delay_minutes'] + 15} min."
        )
    }
