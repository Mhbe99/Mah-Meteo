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


def send_email_trafic_batch(incidents: list):
    """
    Envoie UN SEUL email récapitulatif groupé par type (accidents, bouchons, travaux, etc.).
    Cooldown global de 1h pour éviter le spam.
    """
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("GMAIL_PASSWORD")
    receivers_str = os.getenv("RECEIVER_EMAILS", "")
    receivers = [r.strip() for r in receivers_str.split(",") if r.strip()]

    global _smtp_unreachable

    if not sender or not password or not receivers:
        print("[TRAFIC] Credentials email manquants ou RECEIVER_EMAILS vide")
        return
    if _smtp_unreachable:
        return
    if not incidents:
        return

    # Cooldown global de 1h (pas par route)
    COOLDOWN_FILE = "exports/last_trafic_alerts.json"
    try:
        state = {}
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

        last_batch = state.get("_last_batch")
        if last_batch:
            delta_sec = (datetime.datetime.now() - datetime.datetime.fromisoformat(last_batch)).total_seconds()
            if delta_sec < 3600:
                print(f"[TRAFIC] Cooldown batch actif ({int(delta_sec)}s/3600s)")
                return
    except Exception:
        state = {}

    now_str = datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')

    # --- Grouper les incidents par type (icon) ---
    from collections import defaultdict
    groups = defaultdict(list)
    type_labels = {
        "[CRASH]": "🚗 Accidents",
        "[TRAFFIC]": "🚦 Bouchons / Congestion",
        "[WORK]": "🚧 Travaux",
        "[CLOSED]": "⛔ Routes fermées",
        "[HAZARD]": "⚠️ Dangers",
        "[OTHER]": "📌 Autres incidents",
    }
    for inc in incidents:
        groups[inc.get("icon", "[OTHER]")].append(inc)

    # --- KPIs ---
    total = len(incidents)
    high_count = sum(1 for i in incidents if i["severity"] == "high")
    retard_max = max((i["delay_minutes"] for i in incidents), default=0)

    kpi_html = f"""
    <div style="display:flex;gap:10px;margin-bottom:18px;">
      <div style="flex:1;padding:12px;border-radius:6px;border-left:4px solid #e53e3e;background:#fff5f5;">
        <div style="font-size:22px;font-weight:700;color:#e53e3e;">{high_count}</div>
        <div style="font-size:11px;color:#718096;">Sévères</div>
      </div>
      <div style="flex:1;padding:12px;border-radius:6px;border-left:4px solid #3182ce;background:#ebf8ff;">
        <div style="font-size:22px;font-weight:700;color:#3182ce;">{total}</div>
        <div style="font-size:11px;color:#718096;">Total incidents</div>
      </div>
      <div style="flex:1;padding:12px;border-radius:6px;border-left:4px solid #dd6b20;background:#fffaf0;">
        <div style="font-size:22px;font-weight:700;color:#dd6b20;">+{retard_max} min</div>
        <div style="font-size:11px;color:#718096;">Retard max</div>
      </div>
    </div>"""

    # --- Sections par type ---
    sev_colors = {"high": "#e53e3e", "med": "#dd6b20", "low": "#d69e2e"}
    sev_labels = {"high": "🔴 Élevée", "med": "🟠 Moyenne", "low": "🟡 Faible"}

    sections_html = ""
    for icon_key, label in type_labels.items():
        inc_list = groups.get(icon_key)
        if not inc_list:
            continue

        rows = ""
        for idx, inc in enumerate(inc_list):
            bg = "background:#f7fafc;" if idx % 2 == 0 else ""
            sev = inc["severity"]
            badge = f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;background:{sev_colors.get(sev,"#718096")};color:#fff;font-size:11px;">{sev_labels.get(sev, sev)}</span>'
            rows += f"""<tr style="{bg}">
              <td style="padding:8px 12px;font-size:12px;color:#2d3748;border-bottom:1px solid #e2e8f0;">{inc['route']}</td>
              <td style="padding:8px 12px;font-size:12px;color:#2d3748;border-bottom:1px solid #e2e8f0;">{inc['description']}</td>
              <td style="padding:8px 12px;font-size:12px;color:#2d3748;border-bottom:1px solid #e2e8f0;text-align:center;">+{inc['delay_minutes']} min</td>
              <td style="padding:8px 12px;font-size:12px;border-bottom:1px solid #e2e8f0;text-align:center;">{badge}</td>
              <td style="padding:8px 12px;font-size:11px;color:#718096;border-bottom:1px solid #e2e8f0;">{inc.get('zone_source','')}</td>
            </tr>"""

        sections_html += f"""
        <h3 style="margin:20px 0 10px 0;font-size:14px;color:#2d3748;border-bottom:2px solid #f0f4f8;padding-bottom:6px;">{label} ({len(inc_list)})</h3>
        <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:4px;overflow:hidden;">
          <thead>
            <tr style="background:#edf2f7;">
              <th style="padding:8px 12px;text-align:left;font-size:11px;color:#4a5568;">Route</th>
              <th style="padding:8px 12px;text-align:left;font-size:11px;color:#4a5568;">Description</th>
              <th style="padding:8px 12px;text-align:center;font-size:11px;color:#4a5568;">Retard</th>
              <th style="padding:8px 12px;text-align:center;font-size:11px;color:#4a5568;">Sévérité</th>
              <th style="padding:8px 12px;text-align:left;font-size:11px;color:#4a5568;">Zone</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    subject = f"[MAH METEO] 🚨 Synthèse trafic — {total} incident(s) dont {high_count} sévère(s)"

    body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',Arial,sans-serif;">
<div style="max-width:680px;margin:32px auto;background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">

  <!-- Header -->
  <div style="background:#2c3e50;padding:20px 24px;">
    <div style="font-size:11px;color:#a0aec0;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Mah Météo</div>
    <h1 style="margin:0;font-size:18px;color:#fff;font-weight:600;">🚨 Synthèse Trafic</h1>
    <p style="margin:6px 0 0 0;font-size:13px;color:#90cdf4;">{total} incident(s) détecté(s) le {now_str}</p>
  </div>

  <!-- Body -->
  <div style="padding:24px;">
    {kpi_html}
    {sections_html}
  </div>

  <!-- Footer -->
  <div style="padding:14px 24px;background:#f7fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#a0aec0;">
    Envoyé automatiquement par Mah Météo — {now_str}<br>Ne pas répondre à cet email.
  </div>

</div>
</body>
</html>"""

    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = ", ".join(receivers)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, receivers, msg.as_string())

        print(f"[TRAFIC] Email synthese envoye ({total} incidents)")

        state["_last_batch"] = datetime.datetime.now().isoformat()
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

    # MODE RÉEL — UN SEUL appel TomTom avec bbox englobante (toutes les zones)
    tous_incidents = {}  # dict pour déduplication par ID TomTom

    if not zones:
        return {"incidents": [], "total": 0, "retard_max": 0, "zones_verifiees": 0}

    try:
        # Calculer la bbox globale couvrant toutes les zones + marge 10km
        all_lats = [z.get("lat", 0) for z in zones]
        all_lons = [z.get("lon", 0) for z in zones]
        lat_min = min(all_lats) - 0.10  # ~10km marge
        lat_max = max(all_lats) + 0.10
        lon_min = min(all_lons) - 0.15  # ~10km marge (ajusté pour latitude)
        lon_max = max(all_lons) + 0.15

        # Vérifier que la bbox ne dépasse pas 10 000 km² (limite TomTom)
        # Approximation: 1° lat ≈ 111km, 1° lon ≈ 73km à lat 49°
        area_km2 = (lat_max - lat_min) * 111 * (lon_max - lon_min) * 73
        if area_km2 > 9500:
            # Trop grand — recentrer sur les sites uniquement
            sites_only = [z for z in zones if z.get("type") == "site"]
            if sites_only:
                all_lats = [z["lat"] for z in sites_only]
                all_lons = [z["lon"] for z in sites_only]
            lat_min = min(all_lats) - 0.20
            lat_max = max(all_lats) + 0.20
            lon_min = min(all_lons) - 0.30
            lon_max = max(all_lons) + 0.30
            print(f"[TRAFIC] Bbox réduite (sites uniquement, ~{int((lat_max-lat_min)*111*(lon_max-lon_min)*73)}km²)")

        bbox_str = f"{lon_min},{lat_min},{lon_max},{lat_max}"
        print(f"[TRAFIC] Bbox globale: {bbox_str} (~{int(area_km2)}km²) pour {len(zones)} zone(s)")

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

        # Convertir dict en liste triée par sévérité (high → med → low)
        order = {"high": 0, "med": 1, "low": 2}
        incidents_list = sorted(
            tous_incidents.values(),
            key=lambda x: order.get(x["severity"], 3)
        )

        # Envoyer UN email synthèse si incidents HIGH severity
        global _smtp_unreachable
        _smtp_unreachable = False  # Reset pour ce cycle
        high_incidents = [inc for inc in incidents_list if inc["severity"] == "high"]
        if high_incidents and not _smtp_unreachable:
            send_email_trafic_batch(high_incidents)

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
