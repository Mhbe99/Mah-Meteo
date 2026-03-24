import requests
import datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
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
RENDER_API_URL = "https://mah-meteo.onrender.com/api/meteo/snapshot/add"
GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS", "false").lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET", "geodis-secret-key-2024")
CLIENT_ID = 1  # Par défaut GEODIS-LEMEUX

def get_jwt_token():
    """🔐 Génère un JWT token pour l'authentification Render"""
    try:
        from jose import jwt
    except ImportError:
        print("⚠️ python-jose pas installé — pas de token généré")
        return None
    
    payload = {
        "client_id": CLIENT_ID,
        "username": "geodis-lemeux"
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token


def post_to_render(zone_name: str, temp, wind, direction, precip, cloudcover, uv, risques, ciel):
    """📤 Envoie les données à Render API si on est sur GitHub Actions"""
    if not GITHUB_ACTIONS:
        return  # On est en local, pas besoin d'envoyer
    
    try:
        token = get_jwt_token()
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
            f"{RENDER_API_URL}?client_id={CLIENT_ID}",
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
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
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
OUTPUT_HTML_PATH = "dashboard_meteo.html"

# === COORDONNEES ===
SITES = {
    "Le Meux 🏣": {"lat": 49.378829, "lon": 2.750393},
    "Clairoix 🏣": {"lat": 49.4194, "lon": 2.8328},
}

VOISINS = {
    "Beauvais": {"lat": 49.4304, "lon": 2.0876},
    "Compiègne": {"lat": 49.4176, "lon": 2.8261},
    "Creil": {"lat": 49.2561, "lon": 2.4834},
    "Nogent-sur-Oise": {"lat": 49.2661, "lon": 2.4706},
    "Chantilly": {"lat": 49.1931, "lon": 2.4714},
    "Clermont": {"lat": 49.3763, "lon": 2.4151},
    "Méru": {"lat": 49.2335, "lon": 2.1293},
    "Noyon": {"lat": 49.5786, "lon": 3.0017},
    "Senlis": {"lat": 49.2079, "lon": 2.5849},
    "Montataire": {"lat": 49.2641, "lon": 2.4436},
    "Liancourt": {"lat": 49.3334, "lon": 2.4573},
    "Chaumont-en-Vexin": {"lat": 49.2761, "lon": 1.8759}
}

TOUTES_ZONES = {**SITES, **VOISINS}

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
        if t < 1 and r > 0 and datetime.datetime.now().month in [11, 12, 1, 2]:
            risk.append("❄️ Verglas")
    except:
        pass
    if test_mode or wind > 40:
        risk.append("💨 Vent fort")
    if rain > 5:
        risk.append("🌧️ Alerte pluie")
    if uv >= 8:
        risk.append("🔥 UV fort")
    if test_mode and not risk:  # Force une alerte de test si aucune autre
        risk.append("🧪 TEST ALERTE")
    return "<br>".join(risk) if risk else "✅ RAS"

def save_to_saas_db(zone_name, temp, wind, direction, precip, cloudcover, uv, risques, ciel):
    """Sauvegarde les données météo dans la base SaaS"""
    if not DB_AVAILABLE:
        return
    try:
        db = SessionLocal()
        # Récupérer la zone du client GEODIS
        zone = db.query(Zone).filter(Zone.name.like(f"%{zone_name}%")).first()
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
        
        # 📤 Envoyer aussi à Render si on est sur GitHub Actions
        post_to_render(zone_name, temp, wind, direction, precip, cloudcover, uv, risques, ciel)
        
        db.close()
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde DB {zone_name}: {e}")

# === RÉCUP DONNÉES ===
current_data = {}
forecast_data = {zone: [] for zone in TOUTES_ZONES}

for zone, coord in TOUTES_ZONES.items():
    lat, lon = coord["lat"], coord["lon"]
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max&hourly=precipitation,cloudcover&timezone=auto"
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

        # 🌞 Récupération UV du jour (journée actuelle)
        uv_today = 0
        if "uv_index_max" in data.get("daily", {}) and len(data["daily"]["uv_index_max"]) > 0:
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
            ciel=ciel
        )
    except requests.RequestException as e:
        print(f"Error fetching data for {zone}: {e}")
        continue

    # ✅ ENVOI MAIL EN CAS DE RISQUE
    if "✅ RAS" not in risque:
        send_email_alerte(zone,f"Risque détecté à{zone}:\n{risque.replace('<br>',',')}")
        
        # 📁 ARCHIVAGE DE L'ALERTE POUR HISTORIQUE
        archive_file = os.path.join("exports", "alertes_historique.json")
        try:
            # Charger historique existant
            if os.path.exists(archive_file):
                with open(archive_file, "r", encoding="utf-8") as fh:
                    historique = json.load(fh)
            else:
                historique = []
            
            # Ajouter nouvelle alerte avec timestamp détaillé
            now = datetime.datetime.now()
            historique.append({
                "timestamp": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "jour_semaine": now.strftime("%A"),
                "heure": now.strftime("%H:00"),
                "zone": zone,
                "risques": risque.replace("<br>", " | "),
                "temp": current.get("temperature", "N/A"),
                "wind": current.get("windspeed", "N/A"),
                "rain": precip_now
            })
            
            # Sauvegarder historique
            os.makedirs(os.path.dirname(archive_file), exist_ok=True)
            with open(archive_file, "w", encoding="utf-8") as fh:
                json.dump(historique, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Erreur archivage alerte {zone}: {e}")
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
            tmin = f"{days['temperature_2m_min'][i]}\u00b0C"
            tmax = f"{days['temperature_2m_max'][i]}\u00b0C"
            pluie = float(days['precipitation_sum'][i])
            uv = days["uv_index_max"][i]
            risque = get_risk_icons(0, 0, pluie, uv)
            forecast_data[zone].append({
                "jour": date,
                "tmin": tmin,
                "tmax": tmax,
                "pluie": f"{pluie} mm",
                "uv": uv,
                "risk": risque
            })

from openpyxl import Workbook
import os

EXPORT_PATH = "exports"
os.makedirs(EXPORT_PATH, exist_ok=True)
EXPORT_FILE = os.path.join(EXPORT_PATH, "risques_meteo.xlsx")

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
        alt = os.path.join(EXPORT_PATH, f"risques_meteo_{ts}.xlsx")
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

leaflet_script += """
const points = [
  { name: "Le Meux 🏣", lat: 49.378829, lon: 2.750393 },
  { name: "Clairoix 🏣", lat: 49.4194, lon: 2.8328 },
  { name: "Beauvais", lat: 49.4304, lon: 2.0876 },
  { name: "Compiègne", lat: 49.4176, lon: 2.8261 },
  { name: "Creil", lat: 49.2561, lon: 2.4834 },
  { name: "Nogent-sur-Oise", lat: 49.2661, lon: 2.4706 },
  { name: "Chantilly", lat: 49.1931, lon: 2.4714 },
  { name: "Clermont", lat: 49.3763, lon: 2.4151 },
  { name: "Méru", lat: 49.2335, lon: 2.1293 },
  { name: "Noyon", lat: 49.5786, lon: 3.0017 },
  { name: "Senlis", lat: 49.2079, lon: 2.5849 },
  { name: "Montataire", lat: 49.2641, lon: 2.4436 },
  { name: "Liancourt", lat: 49.3334, lon: 2.4573 },
  { name: "Chaumont-en-Vexin", lat: 49.2761, lon: 1.8759 }
];

let index = 0;
function loopZoom() {
  const p = points[index];
  map.setView([p.lat, p.lon], 12, { animate: true });
  map.eachLayer(function (layer) {
    if (layer.getPopup && layer.getPopup()) {
      const popup = layer.getPopup();
      const content = popup.getContent();
      if (content && content.includes(p.name)) {
        layer.openPopup();
      } else {
        layer.closePopup();
      }
    }
  });
  index = (index + 1) % points.length;
  setTimeout(loopZoom, 12000); // 12s par ville
}
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

print("✅ Dashboard météo mis à jour.")

# === GÉNÉRATION CARTE TV SEULE ===
TEMPLATE_CARTE_PATH = "template_carte.html"
OUTPUT_CARTE_PATH = "carte_tv.html"

with open(TEMPLATE_CARTE_PATH, "r", encoding="utf-8") as f:
    carte_html = f.read()

carte_html = carte_html.replace("<!--CARTE_INTERACTIVE-->", leaflet_script)

with open(OUTPUT_CARTE_PATH, "w", encoding="utf-8") as f:
    f.write(carte_html)

print("✅ Version TV générée dans carte_tv.html") 