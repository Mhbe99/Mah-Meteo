import sys
import io
# Fix encodage Windows (emojis dans les print)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
import datetime
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import json
import time
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# Imports SaaS
try:
    from meteo_saas.backend.database import SessionLocal, Zone, MeteoSnapshot
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("⚠️ BD SaaS non accessible — données non sauvegardées en BD")

# Charger les variables d'environnement
load_dotenv()
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
RECEIVER_EMAILS = os.getenv("RECEIVER_EMAILS").split(",") if os.getenv("RECEIVER_EMAILS") else []

# Variables pour GitHub Actions → Render sync
RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")
RENDER_API_URL = f"{RENDER_URL}/api/meteo/snapshot/add"
RENDER_API_TOKEN = os.getenv("RENDER_API_TOKEN", "")
GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS", "false").lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET", "geodis-secret-key-2024")


def _charger_clients():
    """Charge tous les clients depuis l'API Render (priorité) puis clients.json.
       Les clients self-service enregistrés via le dashboard sont ainsi inclus."""
    clients = []
    seen_usernames = set()

    # Priorité 1 : charger depuis l'API Render (inclut les clients self-service)
    try:
        resp = requests.get(f"{RENDER_URL}/api/service/clients", headers={"X-Service-Secret": JWT_SECRET}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            api_clients = data.get("clients", [])
            for c in api_clients:
                clients.append(c)
                seen_usernames.add(c.get("username"))
            print(f"[CLIENTS] {len(api_clients)} client(s) chargé(s) depuis API Render")
    except Exception as e:
        print(f"[CLIENTS] API Render indisponible: {e} — fallback clients.json")

    # Priorité 2 : compléter avec clients.json (clients pas encore dans l'API)
    try:
        chemin = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "meteo_saas", "data", "clients.json"
        )
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
        for c in data.get("clients", []):
            if c.get("username") not in seen_usernames:
                clients.append(c)
                seen_usernames.add(c.get("username"))
                print(f"[CLIENTS] + {c.get('username')} depuis clients.json")
    except Exception as e:
        print(f"[CLIENTS] Erreur lecture clients.json: {e}")

    print(f"[CLIENTS] Total: {len(clients)} client(s)")
    return clients


def _zones_depuis_client(client):
    """Construit les dicts SITES et VOISINS
       depuis la config d'un client."""
    zones_config = client.get("zones", {})
    sites = {
        z["name"]: {"lat": z["lat"], "lon": z["lon"]}
        for z in zones_config.get("sites", [])
    }
    voisins = {
        z["name"]: {"lat": z["lat"], "lon": z["lon"]}
        for z in zones_config.get("voisins", [])
    }
    return sites, voisins


def get_jwt_token(client_id=1, username="geodis-lemeux"):
    """🔐 Récupère le JWT token pour l'authentification Render
    
    Priorité :
    1. Appel GET /api/service/token sur Render (toujours frais)
    2. RENDER_API_TOKEN (env fallback)
    3. Génération via JWT_SECRET (local dev)
    """
    # Priorité 1: Token frais depuis Render (avec client_id)
    try:
        response = requests.get(
            f"{RENDER_URL}/api/service/token",
            params={"client_id": client_id},
            headers={"X-Service-Secret": JWT_SECRET},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("token") or data.get("access_token")
            if token:
                print("[✅ Token généré par Render]")
                return token
    except Exception as e:
        print(f"[⚠️ Erreur récupération token Render: {e}]")
    
    # Priorité 2: Token pré-configuré depuis env
    if RENDER_API_TOKEN:
        print("[✅ Token depuis env (RENDER_API_TOKEN)]")
        return RENDER_API_TOKEN
    
    # Priorité 3: Générer un token localement (dev/fallback)
    try:
        from jose import jwt
    except ImportError:
        print("[JWT] python-jose pas installé — pas de token généré")
        return None
    
    payload = {
        "client_id": client_id,
        "username": username
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    print("[✅ Token généré localement]")
    return token


def post_to_render(zone_name: str, temp, wind, direction, precip, cloudcover, uv, risques, ciel, client_id=1):
    """📤 Envoie les données à Render API.
       client_id permet le multi-tenant."""
    try:
        token = get_jwt_token(client_id=client_id)
        if not token:
            return
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "zone_name": zone_name,
            "temperature": float(temp) if temp else None,
            "windspeed": float(wind) if wind else None,
            "wind_direction": direction,
            "precipitation": float(precip) if precip else None,
            "cloudcover": float(cloudcover) if cloudcover else None,
            "uv_index": float(uv) if uv else None,
            "risques": risques,
            "ciel": ciel
        }
        
        response = requests.post(
            f"{RENDER_API_URL}?client_id={client_id}",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Snapshot envoyé à Render pour {zone_name}")
        else:
            print(f"⚠️ Erreur Render {response.status_code}: {response.text[:100]}")
    
    except Exception as e:
        print(f"⚠️ Erreur POST vers Render: {str(e)}")


def send_email_alerte(zone, message):
    global SENDER_EMAIL, RECEIVER_EMAILS, GMAIL_PASSWORD

    # --- Limiteur d'envoi d'alertes ---
    # Une alerte par zone toutes les X secondes (ici 1 heure)
    ALERT_COOLDOWN_SECONDS = 3600  # 1 heure
    ALERT_STATE_FILE = os.path.join("exports", "last_alerts.json")

    def load_alert_state():
        try:
            if os.path.exists(ALERT_STATE_FILE):
                with open(ALERT_STATE_FILE, "r", encoding="utf-8") as fh:
                    return json.load(fh)
        except Exception:
            pass
        return {}

    def save_alert_state(state):
        try:
            os.makedirs(os.path.dirname(ALERT_STATE_FILE), exist_ok=True)
            with open(ALERT_STATE_FILE, "w", encoding="utf-8") as fh:
                json.dump(state, fh)
        except Exception:
            pass

    # Charger état et vérifier cooldown
    state = load_alert_state()
    last_iso = state.get(zone)
    if last_iso:
        try:
            last_dt = datetime.datetime.fromisoformat(last_iso)
            delta = (datetime.datetime.now() - last_dt).total_seconds()
            if delta < ALERT_COOLDOWN_SECONDS:
                print(f"⏳ Alerte déjà envoyée pour {zone} il y a {int(delta)}s — suppression d'un envoi supplémentaire.")
                return
        except Exception:
            pass

    subject = f"Alerte météo détectée à {zone}"
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECEIVER_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, GMAIL_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print(f"📧 Alerte envoyée pour {zone} (vers 2 adresses)")
        # mise à jour de l'état d'alerte (dernier envoi)
        try:
            state[zone] = datetime.datetime.now().isoformat()
            save_alert_state(state)
        except Exception:
            pass
    except Exception as e:
        print(f"❌ Erreur envoi email {zone}: {e}")

# === FICHIERS ===
HTML_TEMPLATE_PATH = "template_meteo.html"

# === OUTILS ===
def get_wind_direction(degree):
    directions = ["Nord", "Nord-Est", "Est", "Sud-Est", "Sud", "Sud-Ouest", "Ouest", "Nord-Ouest"]
    idx = round(degree % 360 / 45) % 8
    return directions[idx]

def get_risk_icons(temp, wind, rain, uv, test_mode=False):
    risk = []
    try:
        t = float(temp)
        r = float(rain)
        w = float(wind)
        u = float(uv)
        if t < 1 and r > 0 and datetime.datetime.now().month in [11, 12, 1, 2]:
            risk.append("❄️ Verglas")
    except:
        w = wind
        r = rain
        u = uv
        pass
    if test_mode or w > 40:
        risk.append("💨 Vent fort")
    if r > 5:
        risk.append("🌧️ Alerte pluie")
    # Aligné avec le backend SaaS: UV élevé dès 7, extrême dès 10
    if u >= 10:
        risk.append("🔥 UV extrême")
    elif u >= 7:
        risk.append("🔥 UV fort")
    if test_mode and not risk:  # Force une alerte de test si aucune autre
        risk.append("🧪 TEST ALERTE")
    return "<br>".join(risk) if risk else "✅ RAS"

def save_to_saas_db(zone_name, temp, wind, direction, precip, cloudcover, uv, risques, ciel, client_id=1):
    """Sauvegarde les données météo dans la base SaaS"""
    if not DB_AVAILABLE:
        return
    try:
        db = SessionLocal()
        # Récupérer la zone du client SPÉCIFIQUE (FIX: filtre par client_id)
        zone = db.query(Zone).filter(Zone.client_id == client_id, Zone.name.like(f"%{zone_name}%")).first()
        if not zone:
            db.close()
            return
        
        # Créer snapshot
        snapshot = MeteoSnapshot(
            zone_id=zone.id,
            temperature=float(temp) if temp else None,
            windspeed=float(wind) if wind else None,
            wind_direction=direction,
            precipitation=float(precip) if precip else None,
            cloudcover=float(cloudcover) if cloudcover else None,
            uv_index=float(uv) if uv else None,
            risques=risques,
            ciel=ciel
        )
        db.add(snapshot)
        db.commit()
        db.close()
    except Exception as e:
        print(f"Erreur sauvegarde DB {zone_name}: {e}")


def _executer_pour_client(client):
    """Exécute la collecte complète pour un client.
       Collecte météo, export Excel, génération HTML,
       envoi données vers Render."""

    username = client.get("username", "geodis-lemeux")
    client_id = client.get("id", 1)

    # Charger les zones depuis la config client
    SITES, VOISINS = _zones_depuis_client(client)
    TOUTES_ZONES = {**SITES, **VOISINS}

    print(f"[CLIENT] Début traitement {username} "
          f"— {len(TOUTES_ZONES)} zones")

    # Nom du fichier HTML — GEODIS garde le nom historique
    if username == "geodis-lemeux":
        OUTPUT_HTML_PATH = "dashboard_meteo.html"
    else:
        OUTPUT_HTML_PATH = f"dashboard_meteo_{username}.html"

    # === RÉCUP DONNÉES ===
    current_data = {}
    forecast_data = {zone: [] for zone in TOUTES_ZONES}

    # État des derniers risques archivés par client/zone (pour éviter les répétitions)
    archive_state_file = os.path.join("exports", "last_archive_risks.json")
    try:
        if os.path.exists(archive_state_file):
            with open(archive_state_file, "r", encoding="utf-8") as fh:
                archive_state = json.load(fh)
        else:
            archive_state = {}
    except Exception:
        archive_state = {}

    def _save_archive_state(state):
        try:
            os.makedirs(os.path.dirname(archive_state_file), exist_ok=True)
            with open(archive_state_file, "w", encoding="utf-8") as fh:
                json.dump(state, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    for zone, coord in TOUTES_ZONES.items():
        lat, lon = coord["lat"], coord["lon"]
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max&hourly=precipitation,cloudcover,uv_index&timezone=auto"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()

            current = data.get("current_weather", {})

            # 🌧️ Récupération pluie actuelle depuis hourly
            hourly = data.get("hourly", {})
            precip_now = 0
            if "time" in hourly and "precipitation" in hourly:
                now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
                now_str = now.strftime("%Y-%m-%dT%H:00")
                if now_str in hourly["time"]:
                    idx = hourly["time"].index(now_str)
                    precip_now = hourly["precipitation"][idx]

            # ☁️ Récupération couverture nuageuse actuelle depuis hourly
            cloud_now = 0
            if "time" in hourly and "cloudcover" in hourly:
                now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
                now_str = now.strftime("%Y-%m-%dT%H:00")
                if now_str in hourly["time"]:
                    idx = hourly["time"].index(now_str)
                    cloud_now = hourly["cloudcover"][idx]

            # 🌞 UV courant (horaire), fallback UV max du jour si indisponible
            uv_today = 0
            if "time" in hourly and "uv_index" in hourly:
                if now_str in hourly["time"]:
                    idx = hourly["time"].index(now_str)
                    uv_today = hourly["uv_index"][idx] or 0
            if uv_today == 0 and "uv_index_max" in data.get("daily", {}) and len(data["daily"]["uv_index_max"]) > 0:
                uv_today = data["daily"]["uv_index_max"][0]

            direction = get_wind_direction(current.get("winddirection", 0))
            # 🌦️ Déterminer le ciel selon conditions
            if precip_now > 0:
                ciel = "🌧️"
            elif cloud_now > 75:
                ciel = "☁️"
            elif cloud_now > 40:
                ciel = "🌤️"
            elif current.get("windspeed", 0) > 30:
                ciel = "🌬️"
            else:
                ciel = "☀️"
            risque = get_risk_icons(current.get("temperature", 0), current.get("windspeed", 0), precip_now, uv_today)
            
            # 💾 SAUVEGARDE DANS BD SAAS
            risque_clean = risque.replace("<br>", " | ")
            save_to_saas_db(
                zone_name=zone,
                temp=current.get("temperature", 0),
                wind=current.get("windspeed", 0),
                direction=direction,
                precip=precip_now,
                cloudcover=cloud_now,
                uv=uv_today,
                risques=risque_clean,
                ciel=ciel,
                client_id=client_id
            )
            
            # 📤 TOUJOURS envoyer à Render même si sauvegarde DB locale échoue
            post_to_render(
                zone_name=zone,
                temp=current.get("temperature", 0),
                wind=current.get("windspeed", 0),
                direction=direction,
                precip=precip_now,
                cloudcover=cloud_now,
                uv=uv_today,
                risques=risque_clean,
                ciel=ciel,
                client_id=client_id
            )
        except requests.RequestException as e:
            print(f"Error fetching data for {zone}: {e}")
            continue

        # ✅ ENVOI/ARCHIVAGE seulement sur changement de risque
        if "✅ RAS" not in risque:
            risk_text = risque.replace("<br>", " | ")
            state_key = f"{client_id}:{zone}"
            last_risk = archive_state.get(state_key)
            risk_changed = (last_risk != risk_text)

            if risk_changed:
                send_email_alerte(zone, f"Risque détecté à{zone}:\n{risque.replace('<br>',',')}")
            
                # 📁 ARCHIVAGE DE L'ALERTE POUR HISTORIQUE
                archive_file = os.path.join("exports", "alertes_historique.json")
                try:
                    # Charger historique existant
                    if os.path.exists(archive_file):
                        with open(archive_file, "r", encoding="utf-8") as fh:
                            historique = json.load(fh)
                    else:
                        historique = []

                    # Garder uniquement un historique récent (30 jours) pour éviter l'accumulation infinie
                    now = datetime.datetime.now()
                    cutoff = now - datetime.timedelta(days=30)
                    historique_recent = []
                    for h in historique:
                        try:
                            ts = h.get("timestamp")
                            if not ts:
                                continue
                            h_dt = datetime.datetime.fromisoformat(ts)
                            if h_dt >= cutoff:
                                historique_recent.append(h)
                        except Exception:
                            continue

                    # Nouvelle alerte enrichie avec client_id pour un fallback multi-tenant sûr
                    new_entry = {
                        "timestamp": now.isoformat(),
                        "date": now.strftime("%Y-%m-%d"),
                        "jour_semaine": now.strftime("%A"),
                        "heure": now.strftime("%H:00"),
                        "client_id": client_id,
                        "zone": zone,
                        "risques": risk_text,
                        "temp": current.get("temperature", "N/A"),
                        "wind": current.get("windspeed", "N/A"),
                        "rain": precip_now
                    }

                    # Éviter les doublons sur la même heure / zone / risque / client
                    already_exists = any(
                        h.get("client_id") == new_entry["client_id"]
                        and h.get("zone") == new_entry["zone"]
                        and h.get("risques") == new_entry["risques"]
                        and h.get("date") == new_entry["date"]
                        and h.get("heure") == new_entry["heure"]
                        for h in historique_recent[-200:]
                    )

                    if not already_exists:
                        historique_recent.append(new_entry)

                    # Sauvegarder historique
                    os.makedirs(os.path.dirname(archive_file), exist_ok=True)
                    with open(archive_file, "w", encoding="utf-8") as fh:
                        json.dump(historique_recent, fh, ensure_ascii=False, indent=2)

                    # Mémoriser le dernier risque archivé pour cette zone/client
                    archive_state[state_key] = risk_text
                    _save_archive_state(archive_state)
                except Exception as e:
                    print(f"⚠️ Erreur archivage alerte {zone}: {e}")
            else:
                print(f"ℹ️ Risque inchangé pour {zone} (client {client_id}) — pas de nouvelle alerte archivée")
        else:
            # Le risque est revenu à RAS: on réarme la détection de changement
            state_key = f"{client_id}:{zone}"
            if state_key in archive_state:
                del archive_state[state_key]
                _save_archive_state(archive_state)
        current_data[zone] = {
            "temp": f"{current.get('temperature')}\u00b0C",
            "wind": f"{current.get('windspeed')} km/h",
            "dir": direction,
            "sky": ciel,
            "risk": risque,
            "hour": datetime.datetime.now().strftime("%H:%M:%S"),
            "lat": lat,
            "lon": lon
        }
        if zone in TOUTES_ZONES:
            days = data.get("daily", {})
            for i in range(len(days["time"])):
                date = datetime.datetime.strptime(days["time"][i], "%Y-%m-%d").strftime("%a %d/%m")
                tmin_val = days['temperature_2m_min'][i]
                tmax_val = days['temperature_2m_max'][i]
                tmin = f"{tmin_val}\u00b0C"
                tmax = f"{tmax_val}\u00b0C"
                pluie = float(days['precipitation_sum'][i])
                uv = days["uv_index_max"][i]
                risque = get_risk_icons(tmin_val, 0, pluie, uv)
                forecast_data[zone].append({
                    "jour": date,
                    "tmin": tmin,
                    "tmax": tmax,
                    "pluie": f"{pluie} mm",
                    "uv": uv,
                    "risk": risque
                })

    # 📤 ENVOYER LES PRÉVISIONS À RENDER
    def post_previsions_to_render():
        """Envoie toutes les prévisions en un seul appel POST."""
        try:
            token = get_jwt_token(client_id=client_id, username=username)
            if not token:
                return
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            payload = []
            for zone_name, jours in forecast_data.items():
                for j in jours[:5]:
                    payload.append({
                        "zone_name": zone_name,
                        "jour": j["jour"],
                        "tmin": j["tmin"],
                        "tmax": j["tmax"],
                        "pluie": j["pluie"],
                        "uv": j["uv"],
                        "risques": j["risk"]
                    })
            if payload:
                r = requests.post(
                    f"{RENDER_URL}/api/previsions/add?client_id={client_id}",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                if r.status_code == 200:
                    print(f"✅ {len(payload)} prévisions envoyées à Render")
                else:
                    print(f"⚠️ Erreur envoi prévisions: {r.status_code} {r.text[:100]}")
        except Exception as e:
            print(f"⚠️ Erreur POST prévisions: {e}")

    post_previsions_to_render()

    from openpyxl import Workbook

    EXPORT_PATH = "exports"
    os.makedirs(EXPORT_PATH, exist_ok=True)
    EXPORT_FILE = os.path.join(
        EXPORT_PATH,
        f"risques_meteo_{username}.xlsx"
    )

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wb = Workbook()

    # === Onglet 1 : Sites
    ws_sites = wb.active
    ws_sites.title = "Risques - Sites"

    ws_sites.append([
        "Horodatage", "Zone", "Jour",
        "Temp. Min / Actuel", "Temp. Max / Vent", "Pluie / Direction",
        "UV / Ciel", "Risque"
    ])

    for zone in SITES:
        actuel = current_data.get(zone, {})
        if actuel.get("risk") != "✅ RAS":
            ws_sites.append([
                now_str, zone, "Actuel",
                actuel.get("temp", ""), actuel.get("wind", ""),
                "", actuel.get("sky", ""), actuel.get("risk", "")
            ])
        for jour in forecast_data.get(zone, [])[:5]:
            if jour["risk"] != "✅ RAS":
                ws_sites.append([
                    now_str, zone, jour["jour"],
                    jour["tmin"], jour["tmax"],
                    jour["pluie"], jour["uv"],
                    jour["risk"]
                ])

    # === Onglet 2 : Voisins
    ws_voisins = wb.create_sheet("Risques - Voisins")

    ws_voisins.append([
        "Horodatage", "Zone", "Température", "Vent", "Direction",
        "Ciel", "Risque", "Heure Maj"
    ])

    for zone in VOISINS:
        d = current_data.get(zone, {})
        if d.get("risk") != "✅ RAS":
            ws_voisins.append([
                now_str, zone,
                d.get("temp", ""), d.get("wind", ""), d.get("dir", ""),
                d.get("sky", ""), d.get("risk", ""), d.get("hour", "")
            ])

    # Enregistrement
    if len(ws_sites['A']) > 1 or len(ws_voisins['A']) > 1:
        try:
            wb.save(EXPORT_FILE)
            print(f"📁 Export Excel avec risques : {EXPORT_FILE}")
        except PermissionError:
            # Le fichier est peut-être ouvert par Excel / verrouillé → sauvegarde alternative
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            alt = os.path.join(EXPORT_PATH, f"risques_meteo_{username}_{ts}.xlsx")
            try:
                wb.save(alt)
                print(f"⚠️  Impossible d'écrire {EXPORT_FILE} (verrouillé). Sauvegarde dans {alt}")
            except Exception as e:
                print(f"❌ Erreur lors de la sauvegarde alternative de l'export Excel: {e}")
    else:
        print("🟢 Aucun risque détecté. Aucun export généré.")        

    # === CHARGER LE TEMPLATE ===
    with open(HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # === TABLEAUX ===
    actuel_html = "".join(
        f"<tr><td>{zone}</td><td>{d['temp']}</td><td>{d['wind']}</td><td>{d['dir']}</td><td>{d['sky']}</td><td>{d['risk']}</td><td>{d['hour']}</td></tr>"
        for zone, d in current_data.items() if zone in SITES
    )

    voisin_html = "".join(
        f"<tr><td>{zone}</td><td>{d['temp']}</td><td>{d['wind']}</td><td>{d['dir']}</td><td>{d['sky']}</td><td>{d['risk']}</td><td>{d['hour']}</td></tr>"
        for zone, d in current_data.items() if zone in VOISINS
    )

    prevision_html = "".join(
        f"<tr><td>{zone}</td><td>{j['jour']}</td><td>{j['tmin']}</td><td>{j['tmax']}</td><td>{j['pluie']}</td><td>{j['uv']}</td><td>{j['risk']}</td></tr>"
        for zone, jours in forecast_data.items() if zone in SITES for j in jours[:5]
    )

    # === INJECTION DES DONNÉES ===
    html = html.replace("<!--DONNEES_ACTUELLES-->", actuel_html)
    html = html.replace("<!--DONNEES_VOISINES-->", voisin_html)
    html = html.replace("<!--DONNEES_PREVISIONS-->", prevision_html)

    # === CARTE INTERACTIVE ===
    leaflet_script = """
<div class="section-title">🗺️ Carte Interactive</div>
<div id="map" style="height: 500px; margin-top: 20px;"></div>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script>
const camionIcon = L.divIcon({
  className: 'custom-camion-icon',
  html: '🚚',
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32]
});
const pointIcon = L.divIcon({
  className: 'custom-point-icon',
  html: '📍',
  iconSize: [20, 20],
  iconAnchor: [10, 20],
  popupAnchor: [0, -20]
});
const map = L.map('map').setView([49.4, 2.75], 10);
L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap'
}).addTo(map);
"""

    for zone, d in current_data.items():
        uv = forecast_data.get(zone, [{}])[0].get("uv", "N/A")
        tmin = forecast_data.get(zone, [{}])[0].get("tmin", "N/A")
        tmax = forecast_data.get(zone, [{}])[0].get("tmax", "N/A")
        pluie = forecast_data.get(zone, [{}])[0].get("pluie", "N/A")
        risk_jour = forecast_data.get(zone, [{}])[0].get("risk", "N/A")

        popup = f"""<div style='background:#f2f2f2;padding:8px;border-radius:6px'>
<b>{zone}</b><br>
🌡️ Actuel : {d['temp']}<br>
💨 Vent : {d['wind']} ({d['dir']})<br>
{d['sky']}<br>
🕒 Maj : {d['hour']}<br><br>
📆 Prévisions du jour :<br>
🔻 Tmin : {tmin} / 🔺 Tmax : {tmax}<br>
☔ Pluie : {pluie}<br>
🌞 UV max : {uv}<br>
⚠️ Risques : {risk_jour}
</div>""".replace("\n", "").replace('"', '\\"')

        icon = "camionIcon" if zone in SITES else "pointIcon"
        leaflet_script += f"\nL.marker([{d['lat']}, {d['lon']}], {{ icon: {icon} }}).addTo(map).bindPopup(\"{popup}\");"

    # Points pour la boucle de zoom automatique
    zoom_points = [
        {"name": z, "lat": c["lat"], "lon": c["lon"]}
        for z, c in TOUTES_ZONES.items()
    ]
    zoom_points_js = json.dumps(zoom_points, ensure_ascii=False)

    leaflet_script += f"""
const points = {zoom_points_js};

let index = 0;
function loopZoom() {{
  const p = points[index];
  map.setView([p.lat, p.lon], 12, {{ animate: true }});
  map.eachLayer(function (layer) {{
    if (layer.getPopup && layer.getPopup()) {{
      const popup = layer.getPopup();
      const content = popup.getContent();
      if (content && content.includes(p.name)) {{
        layer.openPopup();
      }} else {{
        layer.closePopup();
      }}
    }}
  }});
  index = (index + 1) % points.length;
  setTimeout(loopZoom, 12000); // 12s par ville
}}
loopZoom();
</script>
"""

    leaflet_script += "</script>"
    html = html.replace("<!--CARTE_INTERACTIVE-->", leaflet_script)

    # ========== TRAFIC TOMTOM ==========
    # Importer les fonctions trafic avec fallback en cas d'erreur
    try:
        from meteo_saas.backend.trafic import get_incidents, get_alerte_combinee
    except ImportError:
        # Fallback si API trafic indisponible
        def get_incidents(z, test_mode=False): 
            return {"incidents": [], "total": 0, "retard_max": 0, "zones_verifiees": 0}
        def get_alerte_combinee(i, r): 
            return None

    # Construire liste zones pour TomTom API
    zones_pour_trafic = []
    for zone, coord in TOUTES_ZONES.items():
        zones_pour_trafic.append({
            "name": zone,
            "lat": coord["lat"],
            "lon": coord["lon"],
            "type": "site" if zone in SITES else "voisin"
        })

    # Appeler TomTom API en mode reel
    try:
        trafic_response = get_incidents(zones_pour_trafic, test_mode=False)
        incidents_list = trafic_response.get("incidents", [])
        retard_max = trafic_response.get("retard_max", 0)
        total_incidents = trafic_response.get("total", 0)
    except Exception as e:
        print(f"[TRAFIC] Erreur API: {e}")
        incidents_list = []
        retard_max = 0
        total_incidents = 0

    # Generer HTML pour incidents trafic
    def severity_label(s):
        """Retourne le label avec emoji pour la severite"""
        labels = {"high": "🔴 Grave", "med": "🟡 Modere", "low": "🟢 Faible"}
        return labels.get(s, s)

    def severity_color(s):
        """Retourne la couleur hex selon la severite"""
        colors = {"high": "#c0392b", "med": "#b8660a", "low": "#27ae60"}
        return colors.get(s, "#888")

    # Generer les lignes du tableau incidents
    trafic_html = ""
    if not incidents_list:
        trafic_html = """
    <tr>
      <td colspan="5" style="text-align:center;color:#888;padding:20px">
        [OK] Aucun incident signalee dans votre zone
      </td>
    </tr>"""
    else:
        for inc in incidents_list:
            couleur = severity_color(inc.get("severity", "low"))
            icon_text = inc.get("icon", "[INCIDENT]")
            trafic_html += f"""
        <tr>
          <td style="border-left:4px solid {couleur};padding-left:8px">
            {icon_text} {inc.get("route", "N/A")}
          </td>
          <td>{inc.get("description", "N/A")}</td>
          <td style="color:{couleur};font-weight:600">
            {severity_label(inc.get("severity", "low"))}
          </td>
          <td style="font-weight:600">
            {f"+{inc.get('delay_minutes', 0)} min" if inc.get("delay_minutes", 0) > 0 else "Faible"}
          </td>
          <td style="color:#888;font-size:11px">{inc.get("zone_source", "")}</td>
        </tr>"""

    # Detecter risques meteo actifs pour alerte combinee
    risques_actifs = [
        f"{zone}: {d['risk']}"
        for zone, d in current_data.items()
        if "✅ RAS" not in d.get("risk", "✅ RAS")
    ]

    # Generer alerte combinee meteor + trafic
    alerte_html = ""
    try:
        alerte_combinee = get_alerte_combinee(incidents_list, risques_actifs)
        if alerte_combinee:
            alerte_html = f"""
    <div style="background:#fff3cd;border:1px solid #f5c542;
                border-left:4px solid #e8530a;border-radius:4px;
                padding:14px 16px;margin-bottom:16px">
      <div style="font-weight:700;color:#b8660a;font-size:12px;
                  text-transform:uppercase;margin-bottom:6px">
        [ALERTE] Meteor + Trafic combinee
      </div>
      <div style="color:#555;font-size:13px">
        {alerte_combinee.get("message", "")}
      </div>
    </div>"""
    except Exception as e:
        print(f"[TRAFIC] Erreur alerte combinee: {e}")
        alerte_html = ""

    # Injector donnees trafic dans template HTML
    html = html.replace("<!--DONNEES_TRAFIC-->", trafic_html)
    html = html.replace("<!--ALERTE_COMBINEE-->", alerte_html)
    html = html.replace("<!--TRAFIC_TOTAL-->", str(total_incidents))
    html = html.replace("<!--TRAFIC_RETARD_MAX-->", f"+{retard_max} min" if retard_max > 0 else "0 min")
    html = html.replace("<!--TRAFIC_MAJ-->", datetime.datetime.now().strftime("%H:%M"))

    # Ajouter marqueurs incidents sur la carte
    trafic_icon_template = """L.divIcon({{
    className: '',
    html: '{icon}',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
}})"""

    for inc in incidents_list:
        if inc.get("lat") and inc.get("lon"):
            icon_html = inc.get("icon", "[TRAFFIC]")
            popup_trafic = (
                f"<div style='font-family:sans-serif;padding:8px;'>"
                f"<b>{inc.get('route', '')}</b><br>"
                f"{inc.get('description', '')}<br>"
                f"Retard : +{inc.get('delay_minutes', 0)} min"
                f"</div>"
            ).replace('"', '\\"')

            icon_js = trafic_icon_template.replace('{icon}', icon_html)
            leaflet_script = leaflet_script.replace(
                "loopZoom();",
                f"L.marker([{inc['lat']}, {inc['lon']}], {{ icon: {icon_js} }})"
                f".addTo(map).bindPopup(\"{popup_trafic}\");\nloopZoom();"
            )


    with open(OUTPUT_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Dashboard météo mis à jour : {OUTPUT_HTML_PATH}")

    # === GÉNÉRATION CARTE TV SEULE ===
    TEMPLATE_CARTE_PATH = "template_carte.html"
    if username == "geodis-lemeux":
        OUTPUT_CARTE_PATH = "carte_tv.html"
    else:
        OUTPUT_CARTE_PATH = f"carte_tv_{username}.html"

    try:
        with open(TEMPLATE_CARTE_PATH, "r", encoding="utf-8") as f:
            carte_html = f.read()

        carte_html = carte_html.replace("<!--CARTE_INTERACTIVE-->", leaflet_script)

        with open(OUTPUT_CARTE_PATH, "w", encoding="utf-8") as f:
            f.write(carte_html)

        print(f"✅ Version TV générée dans {OUTPUT_CARTE_PATH}")
    except Exception as e:
        print(f"⚠️ Erreur génération carte TV: {e}")

    print(f"[CLIENT] Fin traitement {username}")


# === POINT D'ENTRÉE PRINCIPAL ===

if __name__ == "__main__" or os.getenv("GITHUB_ACTIONS"):

    clients = _charger_clients()

    if not clients:
        # Fallback GEODIS si clients.json inaccessible
        print("[CLIENTS] Fallback sur GEODIS uniquement")
        clients = [{
            "id": 1,
            "username": "geodis-lemeux",
            "zones": {
                "sites": [
                    {"name": "Le Meux 🏣", "lat": 49.378829, "lon": 2.750393},
                    {"name": "Clairoix 🏣", "lat": 49.4194, "lon": 2.8328}
                ],
                "voisins": []
            }
        }]

    for client in clients:
        try:
            _executer_pour_client(client)
        except Exception as e:
            print(f"[CLIENTS] Erreur {client.get('username')}: {e}")
            continue
            # On continue avec le client suivant sans tout planter