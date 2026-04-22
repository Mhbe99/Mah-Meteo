# -*- coding: utf-8 -*-
"""
main.py — Application FastAPI principale
"""

import os
import hmac
import ipaddress
import httpx
import secrets
import string
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Request, Header, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Rate-limiting pour protéger /auth/login contre le brute-force
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

from .database import get_db, init_db, init_clients_from_json, SessionLocal, Client, Zone, MeteoSnapshot, PrevisionCache, ConnectionLog, AlerteLog, TrafficIncident
from .auth import create_token, verify_password, get_current_client, hash_password
from .models import LoginRequest, RegisterRequest, TokenResponse, ZoneMeteo, PrevisionJour, TrafficIncident as TrafficIncidentModel, Alerte
from pydantic import BaseModel
from typing import Optional, List
from .clients import get_meteo_actuelle, get_previsions, get_alertes, get_zones
from .trafic import get_incidents
from .email_alerts import send_meteo_alert, send_trafic_alert, send_combined_alert, send_welcome_email

load_dotenv()

ADMIN_PIN = os.getenv("ADMIN_PIN", "1909")


# ============ DÉPENDANCE ADMIN ============

async def require_admin(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> int:
    """Vérifie que l'utilisateur est authentifié ET admin (is_admin=1)."""
    client_id = await get_current_client(authorization)
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client or not client.is_admin:
        raise HTTPException(status_code=403, detail="Accès administrateur requis")
    return client_id


# ============ MODÈLES PYDANTIC ============

class MeteoSnapshotCreate(BaseModel):
    """Modèle pour créer un snapshot météo via API"""
    zone_name: str
    temperature: Optional[float] = None
    windspeed: Optional[float] = None
    wind_direction: Optional[str] = None
    precipitation: Optional[float] = None
    cloudcover: Optional[float] = None
    uv_index: Optional[float] = None
    risques: Optional[str] = None
    ciel: Optional[str] = None


# ============ LIFESPAN (Initialisation au démarrage) ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Événements de démarrage et arrêt de l'appli.
    """
    # Au démarrage
    print("🚀 Démarrage de l'application...")
    init_db()
    init_clients_from_json("meteo_saas/data/clients.json")
    print("✅ Application prête")
    
    yield
    
    # À l'arrêt
    print("🛑 Arrêt de l'application")


# ============ INITIALISATION FASTAPI ============

app = FastAPI(
    title="MétéoFlux SaaS",
    description="Plateforme SaaS de surveillance météo et trafic",
    version="1.0.0",
    lifespan=lifespan
)

# Rate-limiting : 10 tentatives/minute par IP sur /auth/login
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============ CORS ============

# En production (PostgreSQL détecté), seul le domaine Render est autorisé
_db_url = os.getenv("DATABASE_URL", "")
_is_production = "postgresql" in _db_url or "postgres" in _db_url

_allowed_origins = ["https://mah-meteo.onrender.com"]
if not _is_production:
    _allowed_origins += [
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ ROUTES AUTHENTIFICATION ============

# Limites par plan
PLAN_LIMITS = {
    "free":       {"sites": 1, "voisins": 5,  "emails": 1, "changes": 3},
    "standard":   {"sites": 1, "voisins": 5,  "emails": 1, "changes": 3},
    "pro":        {"sites": 3, "voisins": 8,  "emails": 3, "changes": 10},
    "enterprise": {"sites": 5, "voisins": 15, "emails": 5, "changes": 30},
    "groupe":     {"sites": 5, "voisins": 15, "emails": 5, "changes": 30},
}

@limiter.limit("10/minute")
@app.post("/auth/login", response_model=TokenResponse)
def login(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authentification utilisateur.
    Retourne un JWT valide 24h.
    Rate-limit : 10 tentatives/minute par IP.
    """
    # Chercher le client
    client = db.query(Client).filter(Client.username == login_data.username).first()
    
    if not client or not verify_password(login_data.password, client.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides"
        )

    if not client.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte en attente d'approbation par un administrateur"
        )

    # Tracker la connexion
    ua_str = request.headers.get("user-agent", "")
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    device_type = "mobile" if any(k in ua_str.lower() for k in ["mobile", "android", "iphone"]) else "tablet" if "ipad" in ua_str.lower() else "desktop"
    browser = "Chrome" if "Chrome" in ua_str and "Edg" not in ua_str else "Edge" if "Edg" in ua_str else "Firefox" if "Firefox" in ua_str else "Safari" if "Safari" in ua_str else "Autre"
    os_info = "Windows" if "Windows" in ua_str else "Mac" if "Macintosh" in ua_str else "Linux" if "Linux" in ua_str else "iOS" if "iPhone" in ua_str else "Android" if "Android" in ua_str else "Autre"
    # Géolocalisation IP — FIX C2: HTTPS + timeout réduit à 1s + validation IP (anti-SSRF)
    location = ""
    try:
        ipaddress.ip_address(ip)  # Valide que c'est bien une IP
        geo_r = httpx.get(f"https://ip-api.com/json/{ip}?fields=city,country,countryCode", timeout=1)
        if geo_r.status_code == 200:
            geo = geo_r.json()
            city = geo.get("city", "")
            cc = geo.get("countryCode", "")
            location = f"{city}, {cc}" if city else cc
    except Exception:
        pass
    try:
        log = ConnectionLog(client_id=client.id, ip_address=ip, user_agent=ua_str[:500], device_type=device_type, browser=browser, os_info=os_info, location=location)
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()

    # Créer le token
    token = create_token(
        data={"client_id": client.id, "username": client.username}
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        client_id=client.id,
        company_name=client.company_name,
        requires_password_change=client.password_changed_at is None  # Mdp temporaire si jamais changé
    )


# ============ INSCRIPTION SELF-SERVICE ============

@limiter.limit("5/minute")
@app.post("/auth/register")
def register(request: Request, data: RegisterRequest, db: Session = Depends(get_db)):
    """Inscription d'un nouveau client avec plan."""
    if data.plan not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail="Plan invalide")

    # FIX C3: Validation mot de passe non vide et min 8 caractères
    if not data.password or len(data.password.strip()) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractères")

    existing = db.query(Client).filter(Client.username == data.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ce nom d'utilisateur existe déjà")

    client = Client(
        username=data.username,
        password_hash=hash_password(data.password),
        company_name=data.company_name,
        email=data.email,
        plan=data.plan,
        active=0  # En attente d'approbation admin
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    return {"status": "pending", "message": "Inscription enregistrée. Un administrateur doit approuver votre compte."}


# ============ PLANS ============

@app.get("/api/plans")
def get_plans():
    """Retourne les limites de chaque plan."""
    return PLAN_LIMITS


@app.get("/api/account/{client_id}")
def get_account(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Infos du compte : plan, quotas utilisés."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    limits = PLAN_LIMITS.get(client.plan, PLAN_LIMITS["free"])
    return {
        "username": client.username,
        "company_name": client.company_name,
        "email": client.email,
        "plan": client.plan,
        "sites_used": sum(1 for z in zones if z.type == "site"),
        "sites_max": limits["sites"],
        "voisins_used": sum(1 for z in zones if z.type == "voisin"),
        "voisins_max": limits["voisins"],
        "emails_max": limits["emails"],
        "changes_used": client.zone_changes or 0,
        "changes_max": limits["changes"],
    }


# ============ GEOCODING (proxy Open-Meteo) ============

@app.get("/api/geocoding/search")
async def geocoding_search(q: str):
    """Recherche de villes via Open-Meteo Geocoding API."""
    if not q or len(q) < 2:
        return []
    async with httpx.AsyncClient(timeout=5) as http:
        resp = await http.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": q, "count": 8, "language": "fr"}
        )
        data = resp.json()
    results = []
    for r in data.get("results", []):
        results.append({
            "name": r.get("name"),
            "lat": r.get("latitude"),
            "lon": r.get("longitude"),
            "country": r.get("country", ""),
            "admin1": r.get("admin1", ""),
        })
    return results


# ============ GESTION DES ZONES (ajout / suppression) ============

class ZoneAddRequest(BaseModel):
    name: str
    lat: float
    lon: float
    type: str = "voisin"  # "site" ou "voisin"

@app.post("/api/zones/{client_id}/add")
def add_zone(client_id: int, data: ZoneAddRequest, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Ajoute une zone au client (vérifie les limites du plan)."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    limits = PLAN_LIMITS.get(client.plan, PLAN_LIMITS["free"])
    zones = db.query(Zone).filter(Zone.client_id == client_id).all()

    if data.type == "site" and sum(1 for z in zones if z.type == "site") >= limits["sites"]:
        raise HTTPException(status_code=403, detail=f"Limite de {limits['sites']} sites atteinte (plan {client.plan})")

    if data.type == "voisin" and sum(1 for z in zones if z.type == "voisin") >= limits["voisins"]:
        raise HTTPException(status_code=403, detail=f"Limite de {limits['voisins']} villes voisines atteinte (plan {client.plan})")

    # Vérifier doublon
    existing = db.query(Zone).filter(Zone.client_id == client_id, Zone.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"La zone '{data.name}' existe déjà")

    zone = Zone(client_id=client_id, name=data.name, lat=data.lat, lon=data.lon, type=data.type)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return {"status": "ok", "zone_id": zone.id, "name": zone.name}


@app.delete("/api/zones/{client_id}/{zone_id}")
def delete_zone(client_id: int, zone_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Supprime une zone du client."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")
    zone = db.query(Zone).filter(Zone.id == zone_id, Zone.client_id == client_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone introuvable")

    # Vérifier limite de changements (suppression = 1 changement)
    client = db.query(Client).filter(Client.id == client_id).first()
    limits = PLAN_LIMITS.get(client.plan, PLAN_LIMITS["free"])
    changes_used = client.zone_changes or 0
    if changes_used >= limits["changes"]:
        raise HTTPException(status_code=403, detail=f"Limite de {limits['changes']} changements atteinte (plan {client.plan})")

    client.zone_changes = changes_used + 1
    db.delete(zone)
    db.commit()
    return {"status": "ok", "deleted": zone.name}


# ============ ROUTES API — MÉTÉO ============

@app.get("/api/meteo/{client_id}", response_model=list[ZoneMeteo])
def get_meteo(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère les données météo actuelles pour le client.
    Vérifie que l'utilisateur accède UNIQUEMENT à ses propres données.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_meteo_actuelle(client_id, db)


@app.get("/api/previsions/{client_id}", response_model=list[PrevisionJour])
def get_previsions_route(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère les prévisions 5 jours pour le client.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_previsions(client_id, db)


@app.get("/api/alertes/{client_id}", response_model=list[Alerte])
def get_alertes_route(client_id: int, limit: int = Query(default=30, ge=1, le=500), current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère les dernières alertes du client.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_alertes(client_id, db, limit=limit)


@app.get("/api/zones/{client_id}")
def get_zones_route(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère toutes les zones du client.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_zones(client_id, db)


@app.post("/api/meteo/snapshot/add")
def add_meteo_snapshot(
    client_id: int,
    data: MeteoSnapshotCreate,
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    ➕ Ajoute un snapshot météo pour une zone.
    Endpoint utilisé par auto_meteo_loop.py quand ça tourne sur GitHub Actions.
    Authentification par JWT token (Bearer).
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    # Trouver la zone (match exact insensible à la casse)
    zone = db.query(Zone).filter(
        Zone.client_id == client_id,
        Zone.name.ilike(data.zone_name)
    ).first()

    if not zone:
        # Auto-créer la zone si elle existe dans clients.json
        import json as _json
        _json_path = os.path.join(os.path.dirname(__file__), "..", "data", "clients.json")
        _coords = None
        _zone_type = "voisin"
        try:
            with open(_json_path, "r", encoding="utf-8") as _f:
                _clients = _json.load(_f)
            for _c in _clients.get("clients", []):
                for _st, _key in [("site", "sites"), ("voisin", "voisins")]:
                    for _z in _c.get("zones", {}).get(_key, []):
                        if _z["name"].lower() == data.zone_name.lower():
                            _coords = (_z["lat"], _z["lon"])
                            _zone_type = _st
                            break
        except Exception:
            pass
        if not _coords:
            raise HTTPException(status_code=404, detail=f"Zone '{data.zone_name}' not found")
        zone = Zone(client_id=client_id, name=data.zone_name, lat=_coords[0], lon=_coords[1], type=_zone_type)
        db.add(zone)
        db.commit()
        db.refresh(zone)
        print(f"[AUTO] Zone '{data.zone_name}' créée automatiquement")

    # Créer et sauvegarder le snapshot
    snapshot = MeteoSnapshot(
        zone_id=zone.id,
        temperature=data.temperature,
        windspeed=data.windspeed,
        wind_direction=data.wind_direction,
        precipitation=data.precipitation,
        cloudcover=data.cloudcover,
        uv_index=data.uv_index,
        risques=data.risques,
        ciel=data.ciel
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    
    # ✅ METTRE À JOUR LA ZONE avec les dernières données
    zone.temperature = data.temperature
    zone.windspeed = data.windspeed
    zone.wind_direction = data.wind_direction
    zone.precipitation = data.precipitation
    zone.cloudcover = data.cloudcover
    zone.uv_index = data.uv_index
    zone.risques = data.risques
    zone.ciel = data.ciel
    zone.updated_at = datetime.utcnow()
    
    db.add(zone)
    db.commit()

    return {"status": "success", "zone_id": zone.id, "snapshot_id": snapshot.id, "timestamp": snapshot.timestamp}


class PrevisionAdd(BaseModel):
    zone_name: str
    jour: str
    tmin: Optional[str] = None
    tmax: Optional[str] = None
    pluie: Optional[str] = None
    uv: Optional[float] = None
    risques: Optional[str] = None


@app.post("/api/previsions/add")
def add_previsions(
    client_id: int,
    data: list[PrevisionAdd],
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Reçoit les prévisions depuis GitHub Actions et les stocke en cache DB."""
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    # Supprimer l'ancien cache pour ce client
    zone_ids = [z.id for z in db.query(Zone).filter(Zone.client_id == client_id).all()]
    if zone_ids:
        db.query(PrevisionCache).filter(PrevisionCache.zone_id.in_(zone_ids)).delete(synchronize_session=False)

    added = 0
    for prev in data:
        zone = db.query(Zone).filter(
            Zone.client_id == client_id,
            Zone.name.ilike(prev.zone_name)
        ).first()
        if not zone:
            continue
        db.add(PrevisionCache(
            zone_id=zone.id,
            jour=prev.jour,
            tmin=prev.tmin,
            tmax=prev.tmax,
            pluie=prev.pluie,
            uv=prev.uv,
            risques=prev.risques
        ))
        added += 1

    db.commit()
    return {"status": "success", "previsions_added": added}


# ============ ROUTES API — TRAFIC ============

@app.get("/api/trafic/{client_id}")
def get_trafic_route(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère les incidents trafic via TomTom pour le client.
    Retourne les incidents + alerte combinée météo+trafic si applicable.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    # Récupérer les zones du client
    zones_db = db.query(Zone).filter(Zone.client_id == client_id).all()
    zones_list = [{"name": z.name, "lat": z.lat, "lon": z.lon, "type": z.type} for z in zones_db]

    # Récupérer les incidents TomTom — passage en mode RÉEL (test_mode=False)
    from .trafic import get_incidents, get_alerte_combinee
    trafic_response = get_incidents(zones_list, test_mode=False)
    incidents_list = trafic_response.get("incidents", [])

    # Récupérer les risques météo actifs pour alerte combinée
    meteo = get_meteo_actuelle(client_id, db)
    risques_actifs = []
    for zone in meteo:
        # zone est un ZoneMeteo Pydantic model
        risques = getattr(zone, "risques", None)
        if risques and "RAS" not in risques:
            zone_name = getattr(zone, "name", "Zone")
            risques_actifs.append(f"{zone_name}: {risques}")

    alerte_combinee = get_alerte_combinee(incidents_list, risques_actifs)

    # FIX H4: Les emails d'alerte ne doivent PAS être envoyés dans un GET
    # (chaque page load déclencherait des emails). Utiliser un endpoint POST dédié pour les alertes.

    return {
        "incidents": incidents_list,
        "alerte_combinee": alerte_combinee,
        "total": trafic_response.get("total", 0),
        "retard_max": trafic_response.get("retard_max", 0)
    }


# ============ REFRESH MÉTÉO EN DIRECT ============

import math

def _wind_direction_label(deg):
    dirs = ["N","NE","E","SE","S","SO","O","NO"]
    return dirs[round(deg / 45) % 8]

def _ciel_icon(precip, cloud, wind):
    if precip > 0: return "🌧️"
    if cloud > 75: return "☁️"
    if cloud > 40: return "🌤️"
    if wind > 30: return "🌬️"
    return "☀️"

def _risk_text(temp, wind, precip, uv):
    r = []
    if temp >= 35: r.append("🔴 Canicule")
    elif temp <= -5: r.append("🔴 Gel sévère")
    elif temp <= 0: r.append("🟠 Gel")
    if wind >= 80: r.append("🔴 Tempête")
    elif wind >= 50: r.append("🟠 Vent fort")
    if precip >= 10: r.append("🔴 Fortes pluies")
    elif precip >= 3: r.append("🟠 Pluie modérée")
    if uv >= 10: r.append("🔴 UV extrême")
    elif uv >= 7: r.append("🟠 UV élevé")
    return " | ".join(r) if r else "✅ RAS"

@app.post("/api/refresh/{client_id}")
def refresh_meteo(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Rafraîchit les données météo en direct depuis Open-Meteo pour toutes les zones du client.
    Appelé au login du dashboard pour avoir des données fraîches.
    """
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    if not zones:
        return {"status": "ok", "updated": 0}

    updated = 0
    for zone in zones:
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={zone.lat}&longitude={zone.lon}"
                f"&current_weather=true"
                f"&hourly=precipitation,cloudcover,uv_index"
                f"&daily=uv_index_max"
                f"&timezone=auto"
            )
            r = httpx.get(url, timeout=8)
            r.raise_for_status()
            data = r.json()

            current = data.get("current_weather", {})
            hourly = data.get("hourly", {})

            # Heure courante depuis current_weather (timezone-aware)
            current_time = current.get("time", "")  # ex: "2026-04-17T11:00"
            times = hourly.get("time", [])

            # Pluie et nuages à l'heure courante
            precip = 0.0
            cloud = 0.0
            uv = 0.0
            if current_time in times:
                idx = times.index(current_time)
                precip = hourly.get("precipitation", [0.0])[idx] or 0.0
                cloud = hourly.get("cloudcover", [0.0])[idx] or 0.0
                uv = hourly.get("uv_index", [0.0])[idx] or 0.0

            # Fallback: si UV horaire indisponible, utiliser UV max du jour
            if uv == 0.0:
                daily_uv = data.get("daily", {}).get("uv_index_max", [])
                if daily_uv:
                    uv = daily_uv[0] or 0.0

            temp = current.get("temperature", 0)
            wind = current.get("windspeed", 0)
            direction = _wind_direction_label(current.get("winddirection", 0))
            ciel = _ciel_icon(precip, cloud, wind)
            risques = _risk_text(temp, wind, precip, uv)

            zone.temperature = temp
            zone.windspeed = wind
            zone.wind_direction = direction
            zone.precipitation = precip
            zone.cloudcover = cloud
            zone.uv_index = uv
            zone.ciel = ciel
            zone.risques = risques
            from datetime import datetime as _dt
            zone.updated_at = _dt.utcnow()
            updated += 1

        except Exception as e:
            print(f"[REFRESH] Erreur {zone.name}: {e}")
            continue

    db.commit()
    print(f"[REFRESH] {updated}/{len(zones)} zones mises à jour pour client {client_id}")
    return {"status": "ok", "updated": updated, "total": len(zones)}


@app.get("/api/charts/{client_id}")
def get_charts_data(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Données pour les graphiques interactifs du dashboard.
    Retourne les zones_risks depuis la DB + coordonnées de référence.
    Les données hourly/daily sont récupérées côté client (navigateur) directement depuis Open-Meteo.
    """
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    sites = [z for z in zones if z.type == "site"]
    ref = sites[0] if sites else (zones[0] if zones else None)
    if not ref:
        return {"zones_risks": [], "zone_name": "", "ref_lat": 0, "ref_lon": 0}

    # Données risques par zone (pour heatmap)
    zones_risks = []
    for z in zones:
        score = 0
        if z.precipitation and z.precipitation >= 10: score += 3
        elif z.precipitation and z.precipitation >= 3: score += 2
        if z.windspeed and z.windspeed >= 80: score += 3
        elif z.windspeed and z.windspeed >= 50: score += 2
        if z.temperature is not None and z.temperature <= 0: score += 2
        if z.temperature is not None and z.temperature >= 35: score += 3
        if z.uv_index and z.uv_index >= 8: score += 2
        zones_risks.append({"name": z.name, "score": score, "type": z.type or "voisin"})

    return {
        "zone_name": ref.name,
        "ref_lat": ref.lat,
        "ref_lon": ref.lon,
        "zones_risks": zones_risks,
    }


# ============ ROUTES SERVICE (pour meteo_open.py) ============

SERVICE_SECRET = os.getenv("SERVICE_SECRET", os.getenv("JWT_SECRET", "")).strip()

def _verify_service_secret(request: Request):
    """Vérifie que le header X-Service-Secret correspond au JWT_SECRET (ou SERVICE_SECRET si défini)."""
    secret = request.headers.get("X-Service-Secret", "").strip()
    # Accepter JWT_SECRET ET SERVICE_SECRET pour compatibilité cron GitHub Actions
    jwt_secret = os.getenv("JWT_SECRET", "").strip()
    svc_secret = os.getenv("SERVICE_SECRET", "").strip()
    valid_secrets = [s for s in [jwt_secret, svc_secret] if s]
    if not secret or not valid_secrets:
        raise HTTPException(status_code=403, detail="Service secret invalide")
    if not any(hmac.compare_digest(secret.encode(), v.encode()) for v in valid_secrets):
        raise HTTPException(status_code=403, detail="Service secret invalide")

# CORRECTION: Accepter GET et POST pour compatibilité GitHub Actions + meteo_open.py
@app.api_route("/api/service/token", methods=["GET", "POST"])
def get_service_token(request: Request, client_id: int = 1, db: Session = Depends(get_db)):
    """
    🔐 Génère un token JWT pour le service meteo_open.py
    Protégé par X-Service-Secret header.
    """
    _verify_service_secret(request)
    client = db.query(Client).filter(Client.id == client_id).first()
    username = client.username if client else "service-meteo"
    token = create_token(
        data={"client_id": client_id, "username": username}
    )
    return {"token": token, "client_id": client_id, "type": "bearer"}


@app.get("/api/service/clients")
def get_service_clients(request: Request, db: Session = Depends(get_db)):
    """
    📋 Retourne tous les clients actifs + leurs zones.
    Protégé par X-Service-Secret header.
    """
    _verify_service_secret(request)
    clients = db.query(Client).filter(Client.active == 1).all()
    result = []
    for c in clients:
        zones = db.query(Zone).filter(Zone.client_id == c.id).all()
        result.append({
            "id": c.id,
            "username": c.username,
            "company_name": c.company_name,
            "zones": {
                "sites": [{"name": z.name, "lat": z.lat, "lon": z.lon} for z in zones if z.type == "site"],
                "voisins": [{"name": z.name, "lat": z.lat, "lon": z.lon} for z in zones if z.type == "voisin"]
            }
        })
    return {"clients": result}


# ============ CHANGEMENT MOT DE PASSE ============

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

@limiter.limit("5/minute")
@app.post("/api/account/{client_id}/password")
def change_password(client_id: int, data: PasswordChangeRequest, request: Request, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Change le mot de passe du client authentifié.
       Permet le changement sans vérifier l'ancien password si c'est le premier changement (password_changed_at == NULL).
    """
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    
    # Permettre changement sans vérif si c'est le premier changement (password_changed_at == NULL)
    if client.password_changed_at is not None:
        # Pas le premier changement: vérifier l'ancien password
        if not verify_password(data.current_password, client.password_hash):
            raise HTTPException(status_code=401, detail="Mot de passe actuel incorrect")
    
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit faire au moins 8 caractères")
    client.password_hash = hash_password(data.new_password)
    client.password_changed_at = datetime.now()  # Marquer que le mdp a été changé
    db.commit()
    return {"status": "ok", "message": "Mot de passe mis à jour"}


# ============ CONNEXIONS / SESSIONS ============

@app.get("/api/connections/{client_id}")
def get_connections(client_id: int, limit: int = Query(default=50, ge=1, le=200), current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Retourne l'historique des connexions du client."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")
    logs = db.query(ConnectionLog).filter(ConnectionLog.client_id == client_id).order_by(ConnectionLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "ip_address": l.ip_address,
            "device_type": l.device_type,
            "browser": l.browser,
            "os_info": l.os_info,
            "user_agent": l.user_agent,
            "location": l.location or "",
        }
        for l in logs
    ]


# ============ ADMINISTRATION ============

class PinRequest(BaseModel):
    pin: str

@limiter.limit("5/minute")
@app.post("/api/admin/verify-pin")
def verify_admin_pin(data: PinRequest, request: Request, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """Vérifie le PIN admin et retourne si l'utilisateur est admin."""
    client = db.query(Client).filter(Client.id == current_client).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    if data.pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="PIN incorrect")
    if not client.is_admin:
        raise HTTPException(status_code=403, detail="Accès administrateur requis")
    return {"status": "ok", "admin": True}


@app.get("/api/admin/pending")
def get_pending_users(current_client: int = Depends(require_admin), db: Session = Depends(get_db)):
    """Liste les comptes en attente d'approbation."""
    pending = db.query(Client).filter(Client.active == 0).all()
    return [
        {
            "id": c.id,
            "username": c.username,
            "company_name": c.company_name,
            "email": c.email,
            "plan": c.plan,
        }
        for c in pending
    ]


@app.post("/api/admin/approve/{user_id}")
def approve_user(user_id: int, current_client: int = Depends(require_admin), db: Session = Depends(get_db)):
    """Approuve un compte en attente, active essai PRO 7j, et envoie email de bienvenue."""
    user = db.query(Client).filter(Client.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    
    # Générer un mot de passe temporaire fort (12 caractères)
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
    
    # Hacher et assigner le mot de passe
    user.password_hash = hash_password(temp_password)
    user.active = 1
    
    # Ajouter essai PRO gratuit 7 jours (démarre immédiatement)
    user.trial_expires_at = datetime.now() + timedelta(days=7)
    
    # Forcer plan "free" au départ (pour diriger vers upgrade après trial)
    # Les utilisateurs obtiendront accès PRO durant 7j grâce à trial_expires_at
    user.plan = "free"
    user.zone_changes = 0
    user.password_changed_at = None

    # Isolation stricte: un compte nouvellement approuvé doit démarrer sans historique ni zones.
    zone_ids = [zid for (zid,) in db.query(Zone.id).filter(Zone.client_id == user.id).all()]
    if zone_ids:
        db.query(MeteoSnapshot).filter(MeteoSnapshot.zone_id.in_(zone_ids)).delete(synchronize_session=False)
        db.query(PrevisionCache).filter(PrevisionCache.zone_id.in_(zone_ids)).delete(synchronize_session=False)
        db.query(Zone).filter(Zone.client_id == user.id).delete(synchronize_session=False)

    db.query(AlerteLog).filter(AlerteLog.client_id == user.id).delete(synchronize_session=False)
    db.query(TrafficIncident).filter(TrafficIncident.client_id == user.id).delete(synchronize_session=False)
    
    # Récupérer les quotas du plan
    PLAN_LIMITS = {
        "free":       {"sites": 1, "voisins": 3,  "emails": 0, "changes": 2},
        "standard":   {"sites": 1, "voisins": 5,  "emails": 1, "changes": 3},
        "pro":        {"sites": 3, "voisins": 8,  "emails": 3, "changes": 10},
        "enterprise": {"sites": 5, "voisins": 15, "emails": 5, "changes": 30},
        "groupe":     {"sites": 5, "voisins": 15, "emails": 5, "changes": 30},
        "gratuit":    {"sites": 1, "voisins": 3,  "emails": 0, "changes": 2}
    }
    plan_limits = PLAN_LIMITS.get(user.plan or "free", PLAN_LIMITS["free"])
    
    db.commit()
    
    # Envoyer l'email de bienvenue
    try:
        send_welcome_email(
            to_email=user.email,
            username=user.username,
            temp_password=temp_password,
            company_name=user.company_name or "Votre Entreprise",
            plan=user.plan or "free",
            limits=plan_limits,
            trial_expires_at=user.trial_expires_at
        )
        print(f"[APPROVE] Email envoyé à {user.email}")
    except Exception as e:
        print(f"[APPROVE] Erreur envoi email: {e}")
    
    return {"status": "ok", "message": f"Compte {user.username} approuvé et email envoyé"}


@app.post("/api/admin/reject/{user_id}")
def reject_user(user_id: int, current_client: int = Depends(require_admin), db: Session = Depends(get_db)):
    """Rejette et supprime un compte en attente."""
    user = db.query(Client).filter(Client.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    db.delete(user)
    db.commit()
    return {"status": "ok", "message": f"Compte {user.username} rejeté"}


@app.get("/api/admin/all-connections")
def get_all_connections(limit: int = Query(default=100, ge=1, le=200), current_client: int = Depends(require_admin), db: Session = Depends(get_db)):
    """Retourne l'historique de connexions de TOUS les utilisateurs."""
    rows = (
        db.query(ConnectionLog, Client)
        .outerjoin(Client, ConnectionLog.client_id == Client.id)
        .order_by(ConnectionLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    result = []
    for l, client in rows:
        result.append({
            "id": l.id,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "username": client.username if client else "?",
            "company_name": client.company_name if client else "?",
            "ip_address": l.ip_address,
            "location": l.location or "",
            "device_type": l.device_type,
            "browser": l.browser,
            "os_info": l.os_info,
            "user_agent": l.user_agent,
        })
    return result


# ============ ROUTES FRONTEND ============

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """
    Retourne le dashboard HTML avec cache-control pour forcer le rechargement.
    """
    try:
        with open("meteo_saas/frontend/dashboard.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
    except FileNotFoundError:
        return HTMLResponse("<h1>Dashboard introuvable</h1>", status_code=404)


@app.head("/")
async def head_root():
    """FIX: Répond aux HEAD requests pour health checks UptimeRobot/Render"""
    return Response(status_code=200)


@app.get("/health")
def health():
    """Vérification de l'état de l'application"""
    return {"status": "ok"}


@app.get("/api/diagnostics")
def diagnostics(db: Session = Depends(get_db)):
    """Endpoint diagnostique pour tester la connexion BD et détecter les erreurs."""
    try:
        # Test 1: Query the database
        client_count = db.query(Client).count()
        
        # Test 2: Check table structure
        from sqlalchemy import inspect as sqla_inspect
        inspector = sqla_inspect(db.get_bind())
        columns = [c['name'] for c in inspector.get_columns('clients')]
        
        return {
            "status": "ok",
            "database": "connected",
            "client_count": client_count,
            "client_columns": columns,
            "has_trial_expires_at": "trial_expires_at" in columns
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc()
        }


@app.head("/health")
async def head_health():
    """FIX: Répond aux HEAD requests health check"""
    return Response(status_code=200)


# ============ LANCEMENT ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
