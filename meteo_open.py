import sys
import io
# Fix encodage Windows (emojis dans les print)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
import datetime
import os
import json
import time
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from meteo_saas.backend.email_alerts import _envoyer_email

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
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "") or SENDER_EMAIL
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "") or GMAIL_PASSWORD
SMTP_FROM = os.getenv("SMTP_FROM", "") or SENDER_EMAIL
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "3600"))

# Variables pour GitHub Actions → Render sync
RENDER_URL = os.getenv("RENDER_URL", "https://mah-meteo.onrender.com")
RENDER_API_URL = f"{RENDER_URL}/api/meteo/snapshot/add"
RENDER_API_TOKEN = os.getenv("RENDER_API_TOKEN", "")
GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS", "false").lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET", "geodis-secret-key-2024")
_RENDER_SERVICE_TOKEN = None
_RENDER_TOKEN_CHECKED = False
_RENDER_SYNC_DISABLED_REASON = None
_RENDER_SYNC_SKIP_LOGGED = False

# In GitHub Actions the local SQLite schema may be absent; Render sync remains the source of truth.
if GITHUB_ACTIONS and DB_AVAILABLE:
    DB_AVAILABLE = False
    print("[DB] GitHub Actions détecté: sauvegarde DB locale désactivée (sync Render uniquement)")


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
    2. Génération locale via JWT_SECRET seulement pour dev avec secret identique

    Important : RENDER_API_TOKEN n'est pas un JWT applicatif.
    Il ne doit jamais être utilisé comme Bearer sur /api/meteo/snapshot/add.
    """
    global _RENDER_SERVICE_TOKEN, _RENDER_TOKEN_CHECKED, _RENDER_SYNC_DISABLED_REASON

    if _RENDER_TOKEN_CHECKED:
        return _RENDER_SERVICE_TOKEN

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
                _RENDER_SERVICE_TOKEN = token
                _RENDER_TOKEN_CHECKED = True
                print("[✅ Token généré par Render]")
                return token
        # Si Render rejette le service secret, inutile d'insister zone par zone.
        response_excerpt = response.text[:200]
        print(f"[RENDER AUTH] /api/service/token HTTP {response.status_code}: {response_excerpt}")
    except Exception as e:
        print(f"[RENDER AUTH] Erreur récupération token Render: {e}")

    # Fallback local DEV: seulement si l'opérateur connaît le vrai JWT_SECRET de prod.
    try:
        from jose import jwt
    except ImportError:
        print("[JWT] python-jose pas installé — pas de token généré")
        _RENDER_TOKEN_CHECKED = True
        return None

    payload = {
        "client_id": client_id,
        "username": username
    }
    if not JWT_SECRET:
        _RENDER_SYNC_DISABLED_REASON = "JWT_SECRET absent"
        _RENDER_TOKEN_CHECKED = True
        print("[RENDER SYNC] Désactivée: JWT_SECRET absent")
        return None

    # Si le service secret est invalide côté Render, un JWT local serait tout aussi invalide.
    _RENDER_SYNC_DISABLED_REASON = (
        "JWT_SECRET local invalide ou différent de la production ; "
        "RENDER_API_TOKEN n'est pas utilisable comme Bearer applicatif"
    )
    _RENDER_TOKEN_CHECKED = True
    print(f"[RENDER SYNC] Désactivée: {_RENDER_SYNC_DISABLED_REASON}")
    return None


def post_to_render(zone_name: str, temp, wind, direction, precip, cloudcover, uv, risques, ciel, client_id=1,
                   aqi=None, pollution_label=None):
    """📤 Envoie les données à Render API.
       client_id permet le multi-tenant."""
    try:
        global _RENDER_SYNC_SKIP_LOGGED
        token = get_jwt_token(client_id=client_id)
        if not token:
            if not _RENDER_SYNC_SKIP_LOGGED:
                print("[RENDER SYNC] Snapshots ignorés pour ce cycle (auth Render indisponible)")
                _RENDER_SYNC_SKIP_LOGGED = True
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
            "ciel": ciel,
            "aqi": float(aqi) if aqi is not None else None,
            "pollution_label": pollution_label
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


def _load_json_file(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        pass
    return default


def _save_json_file(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _build_email_shell(title, subtitle, content_html, accent="#2c3e50"):
    now_str = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")
    return f"""<!DOCTYPE html>
<html><head><meta charset=\"UTF-8\"></head>
<body style=\"margin:0;padding:0;background:#eef1f5;font-family:'Segoe UI',Arial,sans-serif;\">
  <div style=\"max-width:680px;margin:24px auto;background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;\">
    <div style=\"background:{accent};padding:16px 20px;\">
      <div style=\"font-size:11px;color:#cbd5e0;text-transform:uppercase;letter-spacing:1px;\">Mah Météo</div>
      <div style=\"font-size:18px;color:#fff;font-weight:700;margin-top:4px;\">{title}</div>
      <div style=\"font-size:12px;color:#e2e8f0;margin-top:2px;\">{subtitle}</div>
    </div>
    <div style=\"padding:18px 20px;color:#2d3748;font-size:13px;line-height:1.55;\">{content_html}</div>
    <div style=\"padding:12px 20px;background:#f7fafc;border-top:1px solid #e2e8f0;color:#718096;font-size:11px;\">
      Mah Météo GEODIS · Généré automatiquement · {now_str}
    </div>
  </div>
</body></html>"""


def _send_email_html(subject, html_body):
    # Centralisation: le cron météo ne gère plus le transport lui-même.
    return _envoyer_email(subject, html_body, RECEIVER_EMAILS)


def _split_risk_items(risque_text):
    txt = str(risque_text or "").replace("<br>", " | ")
    items = [x.strip() for x in txt.split("|") if x.strip()]
    unique = []
    for it in items:
        if it not in unique and "RAS" not in it:
            unique.append(it)
    return unique


def _risk_code(item):
    lower = str(item).lower()
    if "verglas" in lower:
        return "verglas"
    if "uv extr" in lower:
        return "uv_extreme"
    if "uv fort" in lower or "uv elev" in lower:
        return "uv_high"
    if "vent" in lower:
        return "wind"
    if "pluie" in lower:
        return "rain"
    return "meteo"


def send_email_alerte_risque(zone, risk_item, context, client_id=1):
    state_path = os.path.join("exports", "last_alerts.json")
    state = _load_json_file(state_path, {})

    key = f"{client_id}:{zone}:{_risk_code(risk_item)}"
    last_iso = state.get(key)
    if last_iso:
        try:
            delta = (datetime.datetime.now() - datetime.datetime.fromisoformat(last_iso)).total_seconds()
            if delta < ALERT_COOLDOWN_SECONDS:
                print(f"⏳ Cooldown actif {key} ({int(delta)}s/{ALERT_COOLDOWN_SECONDS}s)")
                return False
        except Exception:
            pass

    content = f"""
    <p>Risque météo détecté en temps réel sur <strong>{zone}</strong>.</p>
    <div style=\"background:#f7fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 14px;margin:10px 0;\">
      <div style=\"font-size:14px;font-weight:700;color:#c53030;margin-bottom:8px;\">⚠️ {risk_item}</div>
      <div>🌡 Température: <strong>{context.get('temp', 'N/A')}°C</strong></div>
      <div>💨 Vent: <strong>{context.get('wind', 'N/A')} km/h</strong></div>
      <div>🌧 Précipitation: <strong>{context.get('rain', 'N/A')} mm/h</strong></div>
      <div>☀️ UV: <strong>{context.get('uv', 'N/A')}</strong></div>
      <div>☁️ Ciel: <strong>{context.get('ciel', 'N/A')}</strong></div>
    </div>
    <p style=\"color:#718096;font-size:12px;\">Cooldown actif par zone et type de risque: {ALERT_COOLDOWN_SECONDS // 60} minutes.</p>
    """
    body = _build_email_shell("Alerte météo temps réel", f"Zone: {zone}", content, accent="#2c3e50")
    subject = f"⚠️ Alerte météo — {risk_item} — {zone}"

    if _send_email_html(subject, body):
        state[key] = datetime.datetime.now().isoformat()
        _save_json_file(state_path, state)
        print(f"📧 Alerte envoyée [{key}] -> {len(RECEIVER_EMAILS)} destinataire(s)")
        return True
    return False


def send_email_alerte(zone, message):
    # Compatibilité: conserve l'ancien point d'entrée.
    return send_email_alerte_risque(zone=zone, risk_item="Alerte météo", context={"message": message}, client_id=1)

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
    global DB_AVAILABLE
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
        # Disable local DB writes after schema errors to avoid noisy repeated logs.
        if "no such table" in str(e).lower():
            DB_AVAILABLE = False
            print("[DB] Schéma local indisponible, désactivation des écritures DB pour ce run")
        print(f"Erreur sauvegarde DB {zone_name}: {e}")


# ── Échelle AQI européen Open-Meteo ──────────────────────────────────────────
# 0-20 Bon | 20-40 Acceptable | 40-60 Modéré | 60-80 Mauvais | 80-100 Très mauvais | >100 Extrême
def _aqi_label(aqi: float) -> str:
    if aqi is None:
        return "Inconnu"
    if aqi < 20:   return "Bon"
    if aqi < 40:   return "Acceptable"
    if aqi < 60:   return "Modéré"
    if aqi < 80:   return "Mauvais"
    if aqi < 100:  return "Très mauvais"
    return "Extrême"


def fetch_aqi_batch(zone_names: list, zone_coords: list) -> list:
    """
    Récupère l'AQI européen en 1 seule requête Open-Meteo Air Quality
    pour toutes les zones (même principe batch que la météo).
    Retourne une liste de dicts {"aqi": float, "label": str} indexée comme zone_coords.
    """
    lats = ",".join(str(c["lat"]) for c in zone_coords)
    lons = ",".join(str(c["lon"]) for c in zone_coords)
    url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lats}&longitude={lons}"
        f"&current=european_aqi,pm10,pm2_5"
        f"&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        raw = r.json()
        results_raw = raw if isinstance(raw, list) else [raw]
        out = []
        for item in results_raw:
            current = item.get("current", {})
            aqi_val = current.get("european_aqi")
            out.append({
                "aqi": round(aqi_val, 1) if aqi_val is not None else None,
                "label": _aqi_label(aqi_val),
                "pm25": current.get("pm2_5"),
                "pm10": current.get("pm10"),
            })
        print(f"[AQI BATCH] {len(out)} zones récupérées en 1 requête")
        return out
    except Exception as e:
        print(f"[AQI BATCH] Erreur: {e} — AQI ignoré pour ce cycle")
        return [{"aqi": None, "label": "Inconnu", "pm25": None, "pm10": None}] * len(zone_coords)


def send_email_pollution(zones_alertes: list):
    """
    Envoie une alerte email pollution quand AQI >= 40 (3 seuils).
    zones_alertes = [{"zone": str, "aqi": float, "label": str, "pm25": float}, ...]
    
    Seuils et cooldowns:
    - AQI 40-59: Modéré (🟠 orange) — cooldown 6h
    - AQI 60-79: Mauvais (🔴 rouge) — cooldown 3h  
    - AQI 80+: Très mauvais (🔴⛔ bordeaux) — cooldown 1h
    """
    global SENDER_EMAIL, RECEIVER_EMAILS, GMAIL_PASSWORD
    if not zones_alertes or not RECEIVER_EMAILS:
        return

    # Grouper par seuil
    zones_moderate = [z for z in zones_alertes if 40 <= z.get("aqi", 0) < 60]
    zones_bad = [z for z in zones_alertes if 60 <= z.get("aqi", 0) < 80]
    zones_very_bad = [z for z in zones_alertes if z.get("aqi", 0) >= 80]
    
    # Vérifier le cooldown selon le plus haut seuil
    max_aqi = max([z.get("aqi", 0) for z in zones_alertes], default=0)
    if max_aqi >= 80:
        cooldown_seconds = 1 * 3600  # 1h
        cooldown_key = "high"
    elif max_aqi >= 60:
        cooldown_seconds = 3 * 3600  # 3h
        cooldown_key = "medium"
    else:
        cooldown_seconds = 6 * 3600  # 6h
        cooldown_key = "low"

    COOLDOWN_FILE = "exports/last_pollution_alert.json"
    try:
        state = {}
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        last = state.get(cooldown_key)
        if last:
            delta = (datetime.datetime.now() - datetime.datetime.fromisoformat(last)).total_seconds()
            if delta < cooldown_seconds:
                print(f"[POLLUTION] Cooldown {cooldown_key} actif ({int(delta)}s/{cooldown_seconds}s)")
                return
    except Exception:
        state = {}

    now_str = datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')

    def render_section(zones: list, title: str, bg_color: str, border_color: str) -> str:
        if not zones:
            return ""
        rows = ""
        for z in zones:
            pm25_txt = f"{z.get('pm25', 0):.1f} µg/m³" if z.get("pm25") else "—"
            rows += f"""<tr style="border-bottom:1px solid #e2e8f0;">
              <td style="padding:10px 14px;color:#1a202c;font-weight:600;">{z['zone']}</td>
              <td style="padding:10px 14px;text-align:center;font-size:18px;font-weight:700;color:{border_color};">{round(z['aqi'])}</td>
              <td style="padding:10px 14px;text-align:center;color:{border_color};font-weight:600;">{z['label']}</td>
              <td style="padding:10px 14px;text-align:center;color:#4a5568;font-size:12px;">{pm25_txt}</td>
            </tr>"""
        return f"""<div style="margin:12px 0;border-left:4px solid {border_color};background:{bg_color};padding:12px;border-radius:4px;">
          <div style="font-weight:700;color:{border_color};margin-bottom:8px;font-size:13px;">{title}</div>
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead>
              <tr style="background:#f7fafc;">
                <th style="padding:8px 14px;text-align:left;border-bottom:1px solid {border_color};color:#2d3748;font-weight:600;">Site</th>
                <th style="padding:8px 14px;text-align:center;border-bottom:1px solid {border_color};color:#2d3748;font-weight:600;">AQI</th>
                <th style="padding:8px 14px;text-align:center;border-bottom:1px solid {border_color};color:#2d3748;font-weight:600;">Niveau</th>
                <th style="padding:8px 14px;text-align:center;border-bottom:1px solid {border_color};color:#2d3748;font-weight:600;">PM2.5</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    sections_html = ""
    if zones_very_bad:
        sections_html += render_section(zones_very_bad, "⛔ Très mauvais (AQI 80+)", "#fef2f2", "#7b341e")
    if zones_bad:
        sections_html += render_section(zones_bad, "🔴 Mauvais (AQI 60-79)", "#fef2f2", "#e53e3e")
    if zones_moderate:
        sections_html += render_section(zones_moderate, "🟠 Modéré (AQI 40-59)", "#fffbeb", "#dd6b20")

    max_lvl = "Très mauvais" if zones_very_bad else ("Mauvais" if zones_bad else "Modéré")
    subject = f"⚠️ Alerte Pollution — Qualité air {max_lvl}"

    content = f"""
    <p style=\"margin-top:0;\">La qualité de l'air dépasse le seuil d'alerte sur <strong>{len(zones_alertes)} site(s) GEODIS</strong>.</p>
    {sections_html}
    <div style=\"background:#f7fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 14px;margin-top:14px;font-size:11px;color:#718096;line-height:1.5;\">
      <strong>Échelle AQI européen:</strong><br>
      0-20 Bon · 20-40 Acceptable · <strong>40-60 Modéré</strong> · <strong>60-80 Mauvais</strong> · <strong style=\"color:#7b341e;\">80-100 Très mauvais</strong> · >100 Extrême
    </div>
    """
    body = _build_email_shell(
        title="Alerte pollution",
        subtitle=f"Surveillance qualité air — {now_str}",
        content_html=content,
        accent="#744210",
    )

    try:
        if _send_email_html(subject, body):
            counts = f"({len(zones_very_bad)} très mauvais, {len(zones_bad)} mauvais, {len(zones_moderate)} modéré)" if len(zones_alertes) > 1 else ""
            print(f"[POLLUTION] 📧 Alerte envoyée {counts} → {len(RECEIVER_EMAILS)} destinataires")
            state[cooldown_key] = datetime.datetime.now().isoformat()
            os.makedirs("exports", exist_ok=True)
            with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f)
        else:
            print("[POLLUTION] Email non envoyé (SMTP indisponible ou config manquante)")
    except Exception as e:
        print(f"[POLLUTION] Erreur email: {e}")


def _executer_pour_client(client):
    """Exécute la collecte complète pour un client.
       Collecte météo, export Excel, génération HTML,
       envoi données vers Render."""

    username = client.get("username", "geodis-lemeux")
    client_id = client.get("id", 1)

    # Verrou temporaire demande metier: pollution email uniquement sur les 2 sites GEODIS.
    # Cela evite tout envoi inattendu (ex: anciens sites historiques comme Dugny).
    forced_pollution_sites = {"le meux", "clairoix"} if username == "geodis-lemeux" else None

    def _norm_zone_name(name: str) -> str:
        if not name:
            return ""
        txt = str(name).lower().replace("🏣", "")
        txt = "".join(ch for ch in txt if ch.isalnum() or ch in {" ", "-"})
        return " ".join(txt.split())

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

    # ── BATCH Open-Meteo : 1 requête pour toutes les zones (gain ~27×) ──
    zone_names = list(TOUTES_ZONES.keys())
    zone_coords = list(TOUTES_ZONES.values())
    lats = ",".join(str(c["lat"]) for c in zone_coords)
    lons = ",".join(str(c["lon"]) for c in zone_coords)
    batch_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lats}&longitude={lons}"
        f"&current=temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max"
        f"&hourly=precipitation,cloudcover,uv_index"
        f"&temperature_unit=celsius"
        f"&wind_speed_unit=kmh"
        f"&timezone=auto"
    )
    try:
        batch_r = requests.get(batch_url, timeout=30)
        batch_r.raise_for_status()
        batch_raw = batch_r.json()
        # Open-Meteo renvoie un tableau quand plusieurs zones, un objet sinon
        batch_data = batch_raw if isinstance(batch_raw, list) else [batch_raw]
        print(f"[OM BATCH] {len(batch_data)} zones récupérées en 1 requête")
    except Exception as batch_err:
        print(f"[OM BATCH] Erreur: {batch_err} — fallback individuel")
        batch_data = None

    # ── BATCH AQI Open-Meteo Air Quality : 1 requête pour toutes les zones ──
    aqi_batch = fetch_aqi_batch(zone_names, zone_coords)
    # Alerte si AQI >= 40 (3 seuils: Modéré 40-59, Mauvais 60-79, Très mauvais 80+)
    sites_pollution = []
    for zi, (zone, coord) in enumerate(TOUTES_ZONES.items()):
        aqi_info = aqi_batch[zi] if zi < len(aqi_batch) else {}
        aqi_val = aqi_info.get("aqi")
        # Collecte sites avec AQI >= 40 (Modere, Mauvais, Tres mauvais)
        if aqi_val is not None and aqi_val >= 40:
            is_site = zone in SITES
            if not is_site:
                continue
            if forced_pollution_sites is not None and _norm_zone_name(zone) not in forced_pollution_sites:
                print(f"[POLLUTION] Site ignore (hors scope temporaire): {zone}")
                continue
            sites_pollution.append({
                "zone": zone,
                "aqi": aqi_val,
                "label": aqi_info.get("label", "Modéré"),
                "pm25": aqi_info.get("pm25"),
            })
    if sites_pollution:
        max_aqi = max([z["aqi"] for z in sites_pollution])
        alert_lvl = "Très mauvais (80+)" if max_aqi >= 80 else ("Mauvais (60-79)" if max_aqi >= 60 else "Modéré (40-59)")
        print(f"[POLLUTION] ⚠️ {len(sites_pollution)} site(s) en alerte ({alert_lvl}) — envoi email")
        send_email_pollution(sites_pollution)
    else:
        print(f"[POLLUTION] ✅ Qualité de l'air correcte sur tous les sites (AQI < 40)")

    for zi, (zone, coord) in enumerate(TOUTES_ZONES.items()):
        lat, lon = coord["lat"], coord["lon"]
        if batch_data and zi < len(batch_data):
            data = batch_data[zi]
        else:
            # Fallback individuel si batch a échoué
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m"
                f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max"
                f"&hourly=precipitation,cloudcover,uv_index"
                f"&temperature_unit=celsius&wind_speed_unit=kmh&timezone=auto"
            )
            try:
                r = requests.get(url, timeout=25)
                r.raise_for_status()
                data = r.json()
            except requests.RequestException as e:
                print(f"Error fetching data for {zone}: {e}")
                continue
        try:
            current = data.get("current", {})
            legacy_current = data.get("current_weather", {})
            current_time = current.get("time") or legacy_current.get("time") or ""
            temp_now = current.get("temperature_2m")
            if temp_now is None:
                temp_now = legacy_current.get("temperature", 0)
            wind_now = current.get("wind_speed_10m")
            if wind_now is None:
                wind_now = legacy_current.get("windspeed", 0)
            wind_dir_deg = current.get("wind_direction_10m")
            if wind_dir_deg is None:
                wind_dir_deg = legacy_current.get("winddirection", 0)

            # 🌧️ Récupération pluie actuelle depuis hourly
            hourly = data.get("hourly", {})
            precip_now = 0
            if "time" in hourly and "precipitation" in hourly:
                if current_time in hourly["time"]:
                    idx = hourly["time"].index(current_time)
                    precip_now = hourly["precipitation"][idx]

            # ☁️ Récupération couverture nuageuse actuelle depuis hourly
            cloud_now = 0
            if "time" in hourly and "cloudcover" in hourly:
                if current_time in hourly["time"]:
                    idx = hourly["time"].index(current_time)
                    cloud_now = hourly["cloudcover"][idx]

            # 🌞 UV courant (horaire), fallback UV max du jour si indisponible
            uv_today = 0
            if "time" in hourly and "uv_index" in hourly:
                if current_time in hourly["time"]:
                    idx = hourly["time"].index(current_time)
                    uv_today = hourly["uv_index"][idx] or 0
            if uv_today == 0 and "uv_index_max" in data.get("daily", {}) and len(data["daily"]["uv_index_max"]) > 0:
                uv_today = data["daily"]["uv_index_max"][0]

            direction = get_wind_direction(wind_dir_deg or 0)
            # 🌦️ Déterminer le ciel selon conditions
            if precip_now > 0:
                ciel = "🌧️"
            elif cloud_now > 75:
                ciel = "☁️"
            elif cloud_now > 40:
                ciel = "🌤️"
            elif (wind_now or 0) > 30:
                ciel = "🌬️"
            else:
                ciel = "☀️"
            risque = get_risk_icons(temp_now, wind_now, precip_now, uv_today)
            
            # 🌫️ Récupérer AQI pour cette zone depuis le batch
            aqi_info = aqi_batch[zi] if zi < len(aqi_batch) else {}
            aqi_val = aqi_info.get("aqi")
            aqi_lbl = aqi_info.get("label", "Inconnu")

            # 💾 SAUVEGARDE DANS BD SAAS
            risque_clean = risque.replace("<br>", " | ")
            save_to_saas_db(
                zone_name=zone,
                temp=temp_now,
                wind=wind_now,
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
                temp=temp_now,
                wind=wind_now,
                direction=direction,
                precip=precip_now,
                cloudcover=cloud_now,
                uv=uv_today,
                risques=risque_clean,
                ciel=ciel,
                client_id=client_id,
                aqi=aqi_val,
                pollution_label=aqi_lbl
            )
        except Exception as e:
            print(f"Error processing data for {zone}: {e}")
            continue

        # ✅ ENVOI/ARCHIVAGE par type de risque actif (temps réel)
        if "✅ RAS" not in risque:
            archive_file = os.path.join("exports", "alertes_historique.json")
            try:
                historique = _load_json_file(archive_file, [])
                now = datetime.datetime.now()
                cutoff = now - datetime.timedelta(days=30)
                historique_recent = []
                for h in historique:
                    try:
                        ts = h.get("timestamp")
                        if ts and datetime.datetime.fromisoformat(ts) >= cutoff:
                            historique_recent.append(h)
                    except Exception:
                        continue

                for risk_item in _split_risk_items(risque):
                    send_email_alerte_risque(
                        zone=zone,
                        risk_item=risk_item,
                        context={
                            "temp": temp_now,
                            "wind": wind_now,
                            "rain": precip_now,
                            "uv": uv_today,
                            "ciel": ciel,
                        },
                        client_id=client_id,
                    )

                    new_entry = {
                        "timestamp": now.isoformat(),
                        "date": now.strftime("%Y-%m-%d"),
                        "jour_semaine": now.strftime("%A"),
                        "heure": now.strftime("%H:00"),
                        "client_id": client_id,
                        "zone": zone,
                        "risques": risk_item,
                        "temp": temp_now,
                        "wind": wind_now,
                        "rain": precip_now,
                    }
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

                _save_json_file(archive_file, historique_recent)
            except Exception as e:
                print(f"⚠️ Erreur archivage alerte {zone}: {e}")
        current_data[zone] = {
            "temp": f"{temp_now}\u00b0C",
            "wind": f"{wind_now} km/h",
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
                print("[RENDER SYNC] Prévisions non envoyées (auth Render indisponible)")
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

    # === DÉCLENCHEMENT BULLETIN HORAIRE sur Render ===
    # On appelle /api/refresh/{client_id} pour que Render évalue
    # si on est dans un créneau (06h30, 10h30, 12h, 15h, 17h30)
    # et envoie le bulletin email si nécessaire.
    try:
        token_refresh = get_jwt_token(client_id=client_id, username=username)
        if token_refresh:
            r_refresh = requests.post(
                f"{RENDER_URL}/api/refresh/{client_id}",
                headers={"Authorization": f"Bearer {token_refresh}"},
                timeout=30,
            )
            if r_refresh.status_code == 200:
                resp_data = r_refresh.json()
                print(f"[REFRESH] Render OK — {resp_data.get('updated', 0)} zones màj")
            else:
                print(f"[REFRESH] Render {r_refresh.status_code}: {r_refresh.text[:80]}")
    except Exception as _re:
        print(f"[REFRESH] Erreur appel Render refresh: {_re}")

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