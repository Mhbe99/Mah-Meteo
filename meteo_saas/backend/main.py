# -*- coding: utf-8 -*-
"""
main.py — Application FastAPI principale
"""

import os
import json as _json_push
import hmac
import ipaddress
import httpx
import time
from threading import Lock
import secrets
import string
import re
import pytz
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Request, Header, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, text
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Rate-limiting pour protéger /auth/login contre le brute-force
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

from .database import get_db, init_db, init_clients_from_json, SessionLocal, Client, Zone, MeteoSnapshot, PrevisionCache, ConnectionLog, AlerteLog, TrafficIncident, BulletinLog, PushSubscription
from .auth import create_token, verify_password, get_current_client, hash_password, verify_token
from .models import LoginRequest, RegisterRequest, TokenResponse, ZoneMeteo, PrevisionJour, TrafficIncident as TrafficIncidentModel, Alerte
from pydantic import BaseModel
from typing import Optional, List
from .clients import get_meteo_actuelle, get_previsions, get_alertes, get_zones
from .trafic import get_incidents
from .email_alerts import send_meteo_alert, send_trafic_alert, send_combined_alert, send_welcome_email, send_bulletin_email

load_dotenv()

ADMIN_PIN = os.getenv("ADMIN_PIN", "")
COMBINED_ALERT_AUTO_ENABLED = os.getenv("COMBINED_ALERT_AUTO_ENABLED", "true").strip().lower() == "true"
REFRESH_COOLDOWN_SECONDS = int(os.getenv("REFRESH_COOLDOWN_SECONDS", "600"))
DIAGNOSTICS_PUBLIC = os.getenv("DIAGNOSTICS_PUBLIC", "false").strip().lower() == "true"
_refresh_locks: dict[int, Lock] = {}

# ── Bulletins horaires ──
# Créneaux (heure, minute) heure de Paris.
# Fenêtre 31 min par défaut pour capter le refresh horaire de H+1:00
# sur les créneaux en H:30 (ex: 10h30 capté à 11h00).
_BULLETIN_WINDOWS = [
    (6, 0),    # 06h00 brief tournées du matin
    (10, 30),  # 10h30 bilan milieu de matinée
    (12, 0),   # 12h00 départ tournées après-midi
    (15, 0),   # 15h00 bilan milieu d'après-midi
    (17, 30),  # 17h30 fin tournées
]
BULLETIN_WINDOW_MINUTES = int(os.getenv("BULLETIN_WINDOW_MINUTES", "31"))


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
    aqi: Optional[float] = None              # Indice qualité air européen (0-100)
    pollution_label: Optional[str] = None   # "Bon" / "Modéré" / "Mauvais" / "Très mauvais"


class FrontendErrorReport(BaseModel):
    """Rapport d'erreur JavaScript envoyé par le navigateur."""
    kind: str = "error"
    message: str
    source: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    stack: Optional[str] = None
    page_url: Optional[str] = None
    user_agent: Optional[str] = None


class PushSubscriptionModel(BaseModel):
    endpoint: str
    keys: dict
    client_id: int = 1


# ============ LIFESPAN (Initialisation au démarrage) ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Événements de démarrage et arrêt de l'appli.
    """
    # Au démarrage
    print("🚀 Démarrage de l'application...")
    app.state.db_ready = False
    try:
        init_db()
        init_clients_from_json("meteo_saas/data/clients.json")
        app.state.db_ready = True
        print("✅ Application prête")
    except Exception as e:
        # Ne pas bloquer le boot complet en cas de panne DNS/DB temporaire.
        print(f"❌ Démarrage DB échoué: {e}")
        print("⚠️ Application lancée en mode dégradé (DB indisponible)")
    
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

static_dir = os.path.join(
    os.path.dirname(__file__),
    '..', 'static'
)
if os.path.exists(static_dir):
    app.mount(
        "/static",
        StaticFiles(directory=static_dir),
        name="static"
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

@limiter.limit("30/minute")
@app.get("/api/geocoding/search")
async def geocoding_search(request: Request, q: str):
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

@limiter.limit("10/minute")
@app.post("/api/zones/{client_id}/add")
def add_zone(request: Request, client_id: int, data: ZoneAddRequest, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
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

    # Rafraîchissement live à chaque actualisation (même sur GET) pour limiter les écarts de température.
    try:
        refresh_meteo(client_id=client_id, current_client=current_client, db=db)
    except Exception as e:
        print(f"[GET /api/meteo] refresh live indisponible, fallback cache DB: {e}")

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
def get_alertes_route(
    client_id: int,
    limit: int = Query(default=30, ge=1, le=200),
    hours: Optional[int] = Query(default=None, ge=1, le=24 * 30),
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Récupère les dernières alertes du client.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_alertes(client_id, db, limit=limit, hours=hours)


@app.post("/api/alertes/{client_id}/test-email")
def send_test_meteo_alert_email(
    client_id: int,
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Envoie un email de test alerte météo pour valider la configuration SMTP/destinataires."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    zone = db.query(Zone).filter(Zone.client_id == client_id).order_by(Zone.id.asc()).first()
    zone_name = zone.name if zone else "Zone principale"

    send_meteo_alert(
        to_email=(client.email or ""),
        company_name=(client.company_name or client.username or f"Client {client_id}"),
        alertes=[{
            "zone": zone_name,
            "type": "Test prevention",
            "valeur": "Verification envoi email",
            "message": "Email de test pour valider les alertes UV/chaleur en temps reel.",
        }],
        client_id=client_id,
    )

    return {"status": "ok", "message": "Demande d'envoi email de test declenchee"}


@app.post("/api/alertes/{client_id}/test-combined-email")
def send_test_combined_alert_email(
    client_id: int,
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Envoie un email de test pour l'alerte combinee meteo+trafic."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    send_combined_alert(
        to_email=(client.email or ""),
        company_name=(client.company_name or client.username or f"Client {client_id}"),
        message=(
            "Test alerte combinee: risque meteo actif et incident trafic detecte. "
            "Verification du canal email combine."
        ),
        client_id=client_id,
    )

    return {"status": "ok", "message": "Demande d'envoi email combine de test declenchee"}


@app.post("/api/alertes/{client_id}/cleanup-tests")
def cleanup_test_alerts(
    client_id: int,
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Supprime les alertes/snapshots de test et remet les zones a jour."""
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    test_filters = [
        "%TEST REEL%",
        "%ALERTE REELLE%",
        "%Verification envoi email%",
    ]

    zone_ids = [z.id for z in db.query(Zone.id).filter(Zone.client_id == client_id).all()]
    affected_zone_ids = []
    deleted_snapshots = 0
    deleted_alerts = 0

    if zone_ids:
        snapshot_query = db.query(MeteoSnapshot).filter(
            MeteoSnapshot.zone_id.in_(zone_ids),
            or_(*[MeteoSnapshot.risques.ilike(pattern) for pattern in test_filters])
        )
        affected_zone_ids = [row.zone_id for row in snapshot_query.with_entities(MeteoSnapshot.zone_id).distinct().all()]
        deleted_snapshots = snapshot_query.delete(synchronize_session=False)

    deleted_alerts = db.query(AlerteLog).filter(
        AlerteLog.client_id == client_id,
        or_(*[
            AlerteLog.message.ilike(pattern) for pattern in test_filters
        ])
    ).delete(synchronize_session=False)

    db.commit()

    refresh_result = {"status": "skipped", "updated": 0}
    if affected_zone_ids:
        try:
            refresh_result = refresh_meteo(client_id=client_id, current_client=current_client, db=db)
        except Exception as e:
            refresh_result = {"status": "error", "detail": str(e)}

    return {
        "status": "ok",
        "deleted_alert_logs": deleted_alerts,
        "deleted_snapshots": deleted_snapshots,
        "affected_zone_ids": affected_zone_ids,
        "refresh": refresh_result,
    }


@app.get("/api/zones/{client_id}")
def get_zones_route(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Récupère toutes les zones du client.
    """
    if client_id != current_client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")

    return get_zones(client_id, db)


@limiter.limit("120/minute")
@app.post("/api/meteo/snapshot/add")
def add_meteo_snapshot(
    request: Request,
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

    def _norm_zone_name(name: str) -> str:
        # Accepte les variantes avec/sans emoji/suffixes décoratifs
        if not name:
            return ""
        cleaned = re.sub(r"[^\w\s\-]", " ", str(name), flags=re.UNICODE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        return cleaned

    # Trouver la zone (match exact insensible à la casse)
    zone = db.query(Zone).filter(
        Zone.client_id == client_id,
        Zone.name.ilike(data.zone_name)
    ).first()

    # Fallback tolérant (noms avec/sans emoji, espaces, ponctuation)
    if not zone:
        requested = _norm_zone_name(data.zone_name)
        for z in db.query(Zone).filter(Zone.client_id == client_id).all():
            if _norm_zone_name(z.name) == requested:
                zone = z
                break

    if not zone:
        # Auto-créer la zone si elle existe dans clients.json
        import json as _json
        _json_path = os.path.join(os.path.dirname(__file__), "..", "data", "clients.json")
        _coords = None
        _zone_type = "voisin"
        try:
            with open(_json_path, "r", encoding="utf-8") as _f:
                _clients = _json.load(_f)
            requested = _norm_zone_name(data.zone_name)
            for _c in _clients.get("clients", []):
                for _st, _key in [("site", "sites"), ("voisin", "voisins")]:
                    for _z in _c.get("zones", {}).get(_key, []):
                        if _norm_zone_name(_z["name"]) == requested:
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
        ciel=data.ciel,
        aqi=data.aqi,                                      # Indice qualité air
        pollution_label=data.pollution_label                # Label pollution
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
    zone.aqi = data.aqi
    zone.pollution_label = data.pollution_label
    zone.updated_at = datetime.utcnow()
    
    db.add(zone)
    db.commit()

    # Alimenter alertes_log pour les graphes "Mon compte" (Top zones / Répartition type)
    client = db.query(Client).filter(Client.id == client_id).first()
    risques_text = (data.risques or "").strip()
    if risques_text and "RAS" not in risques_text and "✅" not in risques_text:
        now_utc = datetime.utcnow()
        cooldown_cutoff = now_utc - timedelta(hours=1)

        # Déduplication: même client/zone/message déjà logué dans la dernière heure
        deja_log = db.query(AlerteLog).filter(
            AlerteLog.client_id == client_id,
            AlerteLog.zone_name == zone.name,
            AlerteLog.message == risques_text,
            AlerteLog.timestamp >= cooldown_cutoff
        ).first()

        if not deja_log:
            lower = risques_text.lower()
            if "verglas" in lower:
                type_alerte = "verglas"
            elif "vent" in lower:
                type_alerte = "vent_fort"
            elif "pluie" in lower:
                type_alerte = "pluie"
            elif "uv" in lower:
                type_alerte = "uv"
            elif "trafic" in lower:
                type_alerte = "trafic"
            else:
                type_alerte = "meteo"

            db.add(AlerteLog(
                client_id=client_id,
                zone_name=zone.name,
                timestamp=now_utc,
                type_alerte=type_alerte,
                valeur=risques_text,
                message=risques_text
            ))
            db.commit()

            # Envoi email temps reel: seulement lors d'une nouvelle alerte (dedupe 1h deja appliquee)
            try:
                type_labels = {
                    "verglas": "Verglas",
                    "vent_fort": "Vent fort",
                    "pluie": "Alerte pluie",
                    "uv": "UV eleve",
                    "trafic": "Trafic",
                    "meteo": "Alerte meteo",
                }
                alert_type = type_labels.get(type_alerte, "Alerte meteo")
                company_name = (client.company_name if client and client.company_name else (client.username if client else f"Client {client_id}"))
                recipient = (client.email if client and client.email else "")

                send_meteo_alert(
                    to_email=recipient,
                    company_name=company_name,
                    alertes=[{
                        "zone": zone.name,
                        "type": alert_type,
                        "valeur": risques_text,
                        "message": f"Risque detecte: {risques_text}",
                    }],
                    client_id=client_id,
                )
            except Exception as e:
                print(f"[EMAIL] Erreur envoi alerte meteo client {client_id}: {e}")

    return {"status": "success", "zone_id": zone.id, "snapshot_id": snapshot.id, "timestamp": snapshot.timestamp}


class PrevisionAdd(BaseModel):
    zone_name: str
    jour: str
    tmin: Optional[str] = None
    tmax: Optional[str] = None
    pluie: Optional[str] = None
    uv: Optional[float] = None
    risques: Optional[str] = None


@limiter.limit("30/minute")
@app.post("/api/previsions/add")
def add_previsions(
    request: Request,
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

    # Reactive l'alerte combinee auto en restant protege par cooldown email.
    if alerte_combinee and COMBINED_ALERT_AUTO_ENABLED:
        try:
            client = db.query(Client).filter(Client.id == client_id).first()
            if client:
                send_combined_alert(
                    to_email=(client.email or ""),
                    company_name=(client.company_name or client.username or f"Client {client_id}"),
                    message=alerte_combinee,
                    client_id=client_id,
                )
        except Exception as e:
            print(f"[EMAIL] Erreur envoi alerte combinee client {client_id}: {e}")

    # Alerte trafic immédiate standalone : retard ≥ 30 min (sans attendre un créneau)
    retard_max = trafic_response.get("retard_max", 0) or 0
    if retard_max >= 30:
        try:
            gros = [i for i in incidents_list if (i.get("delay_minutes") or 0) >= 30]
            if gros:
                client = db.query(Client).filter(Client.id == client_id).first()
                if client:
                    send_trafic_alert(
                        to_email=(client.email or ""),
                        company_name=(client.company_name or client.username or f"Client {client_id}"),
                        incidents=gros,
                        client_id=client_id,
                    )
        except Exception as e:
            print(f"[EMAIL] Erreur alerte trafic immédiate client {client_id}: {e}")

    return {
        "incidents": incidents_list,
        "alerte_combinee": alerte_combinee,
        "total": trafic_response.get("total", 0),
        "retard_max": retard_max
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


def _get_bulletin_window_label(now=None) -> str | None:
    """
    Retourne le label du créneau actuel (heure Paris)
    ou None si hors fenêtre.
    Tolérance de 30 min par créneau.
    """
    paris = pytz.timezone("Europe/Paris")
    if now is None:
        now = datetime.now(paris)
    elif now.tzinfo is None:
        now = paris.localize(now)
    else:
        now = now.astimezone(paris)

    total_min = now.hour * 60 + now.minute
    for h, m in _BULLETIN_WINDOWS:
        debut = h * 60 + m
        fin = debut + BULLETIN_WINDOW_MINUTES
        if debut <= total_min < fin:
            return f"{h:02d}h{m:02d}"
    return None


def _should_skip_refresh_due_to_cooldown(age_seconds: int, now_paris=None) -> bool:
    """Autorise un refresh forcé pendant les fenêtres bulletin malgré le cooldown."""
    if age_seconds >= REFRESH_COOLDOWN_SECONDS:
        return False
    return _get_bulletin_window_label(now_paris) is None


def _can_send_bulletin(client_id: int, creneau: str, db: Session) -> bool:
    """
    Vérifie si le bulletin du créneau a déjà été envoyé aujourd'hui.
    Utilise la DB pour résister aux redémarrages Render.
    """
    paris = pytz.timezone("Europe/Paris")
    aujourd_hui = datetime.now(paris).strftime("%Y-%m-%d")

    existing = db.query(BulletinLog).filter(
        BulletinLog.client_id == client_id,
        BulletinLog.creneau == creneau,
        BulletinLog.date_jour == aujourd_hui,
    ).first()
    return existing is None


def _mark_bulletin_sent(client_id: int, creneau: str, db: Session) -> None:
    """
    Marque le bulletin comme envoyé en DB.
    Appelé UNIQUEMENT si l'envoi email a réussi.
    """
    paris = pytz.timezone("Europe/Paris")
    aujourd_hui = datetime.now(paris).strftime("%Y-%m-%d")

    try:
        log = BulletinLog(
            client_id=client_id,
            creneau=creneau,
            date_jour=aujourd_hui,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[BULLETIN] Echec persistance bulletin {client_id}/{creneau}: {e}")


def _try_send_bulletin_with_current_data(client_id: int, db: Session) -> None:
    """
    Vérifie si on est dans une fenêtre de bulletin.
    Si oui et pas encore envoyé aujourd'hui -> envoie.
    Lit les données courantes depuis la DB (pas besoin de refresh).
    """
    try:
        paris = pytz.timezone("Europe/Paris")
        maintenant = datetime.now(paris)

        creneau = _get_bulletin_window_label(maintenant)
        if not creneau:
            return

        if not _can_send_bulletin(client_id, creneau, db):
            print(f"[BULLETIN] Déjà envoyé : {creneau} client {client_id}")
            return

        client_obj = db.query(Client).filter(Client.id == client_id).first()
        if not client_obj:
            return

        zones = db.query(Zone).filter(Zone.client_id == client_id).all()
        if not zones:
            print(f"[BULLETIN] Aucune zone pour client {client_id}")
            return

        try:
            zones_list = [
                {"name": z.name, "lat": z.lat, "lon": z.lon, "type": z.type}
                for z in zones
            ]
            trafic_data = get_incidents(zones_list, test_mode=False)
            incidents = trafic_data.get("incidents", [])
        except Exception:
            incidents = []

        to_email = client_obj.email or os.getenv("RECEIVER_EMAILS", "")
        if not to_email:
            print(f"[BULLETIN] Pas de destinataire pour client {client_id}")
            return

        succes = send_bulletin_email(
            to_email=to_email,
            company_name=client_obj.company_name or client_obj.username or f"Client {client_id}",
            zones=zones,
            incidents=incidents,
            creneau=creneau,
        )

        if succes:
            _mark_bulletin_sent(client_id, creneau, db)
            print(f"[BULLETIN] Envoyé : {creneau} -> {to_email}")
        else:
            print(f"[BULLETIN] Echec envoi : {creneau} client {client_id}")
            print("[BULLETIN] Non marqué envoyé : email échoué")
    except Exception as e:
        print(f"[BULLETIN] Erreur évaluation client {client_id}: {e}")


@app.post("/api/refresh/{client_id}")
def refresh_meteo(
    client_id: int,
    force: bool = Query(default=False),
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """
    Rafraîchit les données météo en direct depuis Open-Meteo pour toutes les zones du client.
    Appelé au login du dashboard pour avoir des données fraîches.
    """
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    # Empêche les refresh simultanés pour un même client (rafales multi-onglets / retries frontend).
    lock = _refresh_locks.setdefault(client_id, Lock())
    if not lock.acquire(blocking=False):
        return {
            "status": "ok",
            "updated": 0,
            "total": 0,
            "skipped": "refresh_in_progress",
            "forced": force,
        }

    try:
        zones = db.query(Zone).filter(Zone.client_id == client_id).all()
        if not zones:
            _try_send_bulletin_with_current_data(client_id, db)
            return {"status": "ok", "updated": 0, "forced": force}

        # Cooldown côté serveur: évite de sur-solliciter Open-Meteo quand la vue générale déclenche plusieurs refresh.
        paris_now = datetime.now(pytz.timezone("Europe/Paris"))
        last_updates = [z.updated_at for z in zones if z.updated_at]
        if last_updates:
            freshest = max(last_updates)
            age_seconds = int((datetime.utcnow() - freshest).total_seconds())
            if not force and _should_skip_refresh_due_to_cooldown(age_seconds, paris_now):
                remaining = REFRESH_COOLDOWN_SECONDS - age_seconds
                _try_send_bulletin_with_current_data(client_id, db)
                return {
                    "status": "ok",
                    "updated": 0,
                    "total": len(zones),
                    "skipped": "cooldown",
                    "cooldown_remaining": remaining,
                    "forced": force,
                }

        def _fetch_json_with_retries(url: str, retries: int = 3):
            last_err = None
            for i in range(retries):
                try:
                    resp = httpx.get(url, timeout=25)
                    if resp.status_code in (429, 500, 502, 503, 504):
                        raise RuntimeError(f"HTTP {resp.status_code}")
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    last_err = e
                    # Si on est rate-limited, ne pas insister et ne pas aggraver le quota.
                    if "HTTP 429" in str(e):
                        break
                    if i < retries - 1:
                        time.sleep(0.8 * (i + 1))
            raise last_err

        def _apply_zone_data(zone, data):
            current = data.get("current", {})
            legacy_current = data.get("current_weather", {})
            hourly = data.get("hourly", {})

            current_time = current.get("time") or legacy_current.get("time") or ""
            times = hourly.get("time", [])

            precip = 0.0
            cloud = 0.0
            uv = 0.0
            if current_time in times:
                idx = times.index(current_time)
                precip = hourly.get("precipitation", [0.0])[idx] or 0.0
                cloud = hourly.get("cloudcover", [0.0])[idx] or 0.0
                uv = hourly.get("uv_index", [0.0])[idx] or 0.0

            if uv == 0.0:
                daily_uv = data.get("daily", {}).get("uv_index_max", [])
                if daily_uv:
                    uv = daily_uv[0] or 0.0

            temp = current.get("temperature_2m")
            if temp is None:
                temp = legacy_current.get("temperature", 0)

            wind = current.get("wind_speed_10m")
            if wind is None:
                wind = legacy_current.get("windspeed", 0)

            wind_dir = current.get("wind_direction_10m")
            if wind_dir is None:
                wind_dir = legacy_current.get("winddirection", 0)

            zone.temperature = temp
            zone.windspeed = wind
            zone.wind_direction = _wind_direction_label(wind_dir)
            zone.precipitation = precip
            zone.cloudcover = cloud
            zone.uv_index = uv
            zone.ciel = _ciel_icon(precip, cloud, wind)
            zone.risques = _risk_text(temp, wind, precip, uv)
            zone.updated_at = datetime.utcnow()

        updated = 0
        lats = ",".join(str(z.lat) for z in zones)
        lons = ",".join(str(z.lon) for z in zones)
        batch_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lats}&longitude={lons}"
            f"&current=temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m"
            f"&hourly=precipitation,cloudcover,uv_index"
            f"&daily=uv_index_max"
            f"&temperature_unit=celsius"
            f"&wind_speed_unit=kmh"
            f"&timezone=auto"
        )

        batch_data = None
        batch_rate_limited = False
        try:
            raw = _fetch_json_with_retries(batch_url, retries=3)
            batch_data = raw if isinstance(raw, list) else [raw]
        except Exception as e:
            if "HTTP 429" in str(e):
                batch_rate_limited = True
                print("[REFRESH] Batch Open-Meteo rate-limited (HTTP 429) — fallback unitaire annulé")
            else:
                print(f"[REFRESH] Batch Open-Meteo indisponible: {e} — fallback unitaire")

        if batch_rate_limited:
            _try_send_bulletin_with_current_data(client_id, db)
            return {
                "status": "ok",
                "updated": 0,
                "total": len(zones),
                "skipped": "rate_limited",
                "forced": force,
            }

        for idx, zone in enumerate(zones):
            try:
                if batch_data and idx < len(batch_data):
                    data = batch_data[idx]
                else:
                    url = (
                        f"https://api.open-meteo.com/v1/forecast?"
                        f"latitude={zone.lat}&longitude={zone.lon}"
                        f"&current=temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m"
                        f"&hourly=precipitation,cloudcover,uv_index"
                        f"&daily=uv_index_max"
                        f"&temperature_unit=celsius"
                        f"&wind_speed_unit=kmh"
                        f"&timezone=auto"
                    )
                    data = _fetch_json_with_retries(url, retries=3)

                _apply_zone_data(zone, data)
                updated += 1
            except Exception as e:
                print(f"[REFRESH] Erreur {zone.name}: {e}")
                continue

        db.commit()
        print(f"[REFRESH] {updated}/{len(zones)} zones mises à jour pour client {client_id}")

        # ── Bulletin horaire ──────────────────────────────────────────────────
        _try_send_bulletin_with_current_data(client_id, db)
        # ─────────────────────────────────────────────────────────────────────

        return {"status": "ok", "updated": updated, "total": len(zones), "forced": force}
    finally:
        lock.release()


@app.get("/api/charts/{client_id}")
def get_charts_data(
    client_id: int,
    zone_name: Optional[str] = Query(default=None),
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Données pour les graphiques interactifs du dashboard.
    Retourne les zones_risks depuis la DB + coordonnées de référence + séries hourly/daily.
    En production, les séries sont construites côté backend pour éviter les erreurs CORS/429 côté navigateur.
    """
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    def _norm_zone_name(name: str) -> str:
        if not name:
            return ""
        cleaned = re.sub(r"[^\w\s\-]", " ", str(name), flags=re.UNICODE)
        return re.sub(r"\s+", " ", cleaned).strip().lower()

    def _to_float(value, default=0.0):
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        txt = str(value).replace(",", ".")
        m = re.search(r"-?\d+(?:\.\d+)?", txt)
        return float(m.group(0)) if m else default

    def _build_db_fallback_series(zone_obj: Zone):
        now_utc = datetime.utcnow()
        cutoff = now_utc - timedelta(hours=48)

        snapshots = (
            db.query(MeteoSnapshot)
            .filter(MeteoSnapshot.zone_id == zone_obj.id, MeteoSnapshot.timestamp >= cutoff)
            .order_by(MeteoSnapshot.timestamp.asc())
            .all()
        )

        hourly_fb = [
            {
                "time": s.timestamp.isoformat(),
                "temp": _to_float(s.temperature),
                "precip": _to_float(s.precipitation),
                "wind": _to_float(s.windspeed),
                "cloud": _to_float(s.cloudcover),
            }
            for s in snapshots
        ]

        cache_rows = (
            db.query(PrevisionCache)
            .filter(PrevisionCache.zone_id == zone_obj.id)
            .order_by(PrevisionCache.updated_at.asc(), PrevisionCache.id.asc())
            .all()
        )

        daily_fb = []
        if cache_rows:
            latest = max((r.updated_at for r in cache_rows if r.updated_at), default=None)
            if latest:
                cache_rows = [r for r in cache_rows if r.updated_at and r.updated_at >= (latest - timedelta(hours=8))]

            seen_days = set()
            today = datetime.utcnow().date()
            for row in cache_rows:
                day_key = (row.jour or "").strip().lower()
                if day_key in seen_days:
                    continue
                seen_days.add(day_key)
                idx = len(daily_fb)
                daily_fb.append({
                    "date": (today + timedelta(days=idx)).isoformat(),
                    "tmax": _to_float(row.tmax),
                    "tmin": _to_float(row.tmin),
                    "precip": _to_float(row.pluie),
                    "wind": 0.0,
                    "uv": _to_float(row.uv),
                })
                if len(daily_fb) >= 7:
                    break

        return hourly_fb, daily_fb

    def _build_series(zone_obj: Zone):
        hourly = []
        daily = []
        try:
            om_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={zone_obj.lat}&longitude={zone_obj.lon}"
                f"&hourly=temperature_2m,precipitation,wind_speed_10m,cloudcover"
                f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,uv_index_max"
                f"&past_days=1&forecast_days=7&timezone=auto"
            )
            om_res = httpx.get(om_url, timeout=12)
            if om_res.status_code == 200:
                om = om_res.json()
                h = om.get("hourly") or {}
                times = h.get("time") or []
                temps = h.get("temperature_2m") or []
                precs = h.get("precipitation") or []
                winds = h.get("wind_speed_10m") or h.get("windspeed_10m") or []
                clouds = h.get("cloudcover") or []
                for i in range(len(times)):
                    hourly.append({
                        "time": times[i],
                        "temp": _to_float(temps[i] if i < len(temps) else 0),
                        "precip": _to_float(precs[i] if i < len(precs) else 0),
                        "wind": _to_float(winds[i] if i < len(winds) else 0),
                        "cloud": _to_float(clouds[i] if i < len(clouds) else 0),
                    })
                if len(hourly) > 48:
                    hourly = hourly[-48:]

                d = om.get("daily") or {}
                d_times = d.get("time") or []
                d_tmax = d.get("temperature_2m_max") or []
                d_tmin = d.get("temperature_2m_min") or []
                d_prec = d.get("precipitation_sum") or []
                d_wind = d.get("wind_speed_10m_max") or d.get("windspeed_10m_max") or []
                d_uv = d.get("uv_index_max") or []
                for i in range(len(d_times)):
                    daily.append({
                        "date": d_times[i],
                        "tmax": _to_float(d_tmax[i] if i < len(d_tmax) else 0),
                        "tmin": _to_float(d_tmin[i] if i < len(d_tmin) else 0),
                        "precip": _to_float(d_prec[i] if i < len(d_prec) else 0),
                        "wind": _to_float(d_wind[i] if i < len(d_wind) else 0),
                        "uv": _to_float(d_uv[i] if i < len(d_uv) else 0),
                    })
            elif om_res.status_code == 429:
                print(f"[charts] Open-Meteo 429 for zone {zone_obj.name}, fallback DB")
        except Exception as e:
            print(f"[charts] Open-Meteo unavailable for zone {zone_obj.name}: {e}")

        fb_hourly, fb_daily = _build_db_fallback_series(zone_obj)
        if not hourly:
            hourly = fb_hourly
        if not daily:
            daily = fb_daily
        return hourly, daily

    zones = db.query(Zone).filter(Zone.client_id == client_id).all()
    sites = [z for z in zones if z.type == "site"]
    ref = None
    if zone_name:
        target = _norm_zone_name(zone_name)
        for z in zones:
            if _norm_zone_name(z.name) == target:
                ref = z
                break
    if ref is None:
        ref = sites[0] if sites else (zones[0] if zones else None)

    if not ref:
        return {"zones_risks": [], "zone_name": "", "ref_lat": 0, "ref_lon": 0, "hourly": [], "daily": []}

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
        if z.uv_index and z.uv_index >= 7: score += 2
        zones_risks.append({"name": z.name, "score": score, "type": z.type or "voisin"})

    hourly, daily = _build_series(ref)

    return {
        "zone_name": ref.name,
        "ref_lat": ref.lat,
        "ref_lon": ref.lon,
        "zones_risks": zones_risks,
        "hourly": hourly,
        "daily": daily,
    }


@app.get("/api/pollution/weekly/{client_id}")
def get_pollution_weekly(client_id: int, current_client: int = Depends(get_current_client), db: Session = Depends(get_db)):
    """
    Retourne l'evolution AQI (pollution) sur les 7 derniers jours pour les sites du client.
    """
    if client_id != current_client:
        raise HTTPException(status_code=403, detail="Accès refusé")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    end_day = datetime.utcnow().date()
    start_day = end_day - timedelta(days=6)

    sites = db.query(Zone).filter(Zone.client_id == client_id, Zone.type == "site").all()

    # Scope temporaire demandé métier pour GEODIS: uniquement Le Meux + Clairoix.
    if client.username == "geodis-lemeux":
        allowed = {"le meux", "clairoix"}

        def _norm(n: str) -> str:
            txt = (n or "").lower().replace("🏣", "")
            txt = "".join(ch for ch in txt if ch.isalnum() or ch in {" ", "-"})
            return " ".join(txt.split())

        sites = [s for s in sites if _norm(s.name) in allowed]

    if not sites:
        return {
            "labels": [(start_day + timedelta(days=i)).strftime("%d/%m") for i in range(7)],
            "series": [],
            "thresholds": {"good": 40, "moderate": 60, "bad": 80}
        }

    site_ids = [s.id for s in sites]
    day_start_dt = datetime.combine(start_day, datetime.min.time())

    snaps = db.query(MeteoSnapshot).filter(
        MeteoSnapshot.zone_id.in_(site_ids),
        MeteoSnapshot.timestamp >= day_start_dt,
        MeteoSnapshot.aqi.isnot(None)
    ).all()

    # (zone_id, day) -> moyenne AQI
    bucket = defaultdict(list)
    for s in snaps:
        bucket[(s.zone_id, s.timestamp.date())].append(float(s.aqi))

    labels = [(start_day + timedelta(days=i)).strftime("%d/%m") for i in range(7)]
    days = [start_day + timedelta(days=i) for i in range(7)]

    series = []
    for z in sorted(sites, key=lambda x: x.name.lower()):
        values = []
        for d in days:
            vals = bucket.get((z.id, d), [])
            values.append(round(sum(vals) / len(vals), 1) if vals else None)
        series.append({"name": z.name, "data": values})

    return {
        "labels": labels,
        "series": series,
        "thresholds": {"good": 40, "moderate": 60, "bad": 80}
    }


# ============ ROUTES SERVICE (pour meteo_open.py) ============

SERVICE_SECRET = os.getenv("SERVICE_SECRET", os.getenv("JWT_SECRET", "")).strip()

def _verify_service_secret(request: Request):
    """Valide le secret service via X-Service-Secret/X-Service-Key ou Authorization Bearer.

    Secrets acceptés: JWT_SECRET, SERVICE_SECRET, RENDER_API_TOKEN.
    """
    secret = request.headers.get("X-Service-Secret", "").strip()
    if not secret:
        secret = request.headers.get("X-Service-Key", "").strip()
    if not secret:
        auth = request.headers.get("Authorization", "").strip()
        if auth.lower().startswith("bearer "):
            secret = auth.split(" ", 1)[1].strip()

    # Accepter JWT_SECRET, SERVICE_SECRET et RENDER_API_TOKEN pour compatibilité CI/Render
    jwt_secret = os.getenv("JWT_SECRET", "").strip()
    svc_secret = os.getenv("SERVICE_SECRET", "").strip()
    render_api_token = os.getenv("RENDER_API_TOKEN", "").strip()
    valid_secrets = [s for s in [jwt_secret, svc_secret, render_api_token] if s]
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


class AdminSetPasswordRequest(BaseModel):
    new_password: str


class AdminWelcomeEmailTestRequest(BaseModel):
    to_email: Optional[str] = None

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


@app.post("/api/admin/reset-account/{user_id}")
def reset_account_data(user_id: int, current_client: int = Depends(require_admin), db: Session = Depends(get_db)):
    """Remet un compte client à zéro (données métier uniquement)."""
    user = db.query(Client).filter(Client.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    zone_ids = [zid for (zid,) in db.query(Zone.id).filter(Zone.client_id == user.id).all()]
    deleted_snapshots = 0
    deleted_previsions = 0
    deleted_zones = 0
    if zone_ids:
        deleted_snapshots = db.query(MeteoSnapshot).filter(MeteoSnapshot.zone_id.in_(zone_ids)).delete(synchronize_session=False)
        deleted_previsions = db.query(PrevisionCache).filter(PrevisionCache.zone_id.in_(zone_ids)).delete(synchronize_session=False)
        deleted_zones = db.query(Zone).filter(Zone.client_id == user.id).delete(synchronize_session=False)

    deleted_alertes = db.query(AlerteLog).filter(AlerteLog.client_id == user.id).delete(synchronize_session=False)
    deleted_trafic = db.query(TrafficIncident).filter(TrafficIncident.client_id == user.id).delete(synchronize_session=False)

    user.zone_changes = 0
    db.commit()

    return {
        "status": "ok",
        "message": f"Compte {user.username} remis à zéro",
        "deleted": {
            "zones": deleted_zones,
            "snapshots": deleted_snapshots,
            "previsions": deleted_previsions,
            "alertes": deleted_alertes,
            "trafic": deleted_trafic,
        }
    }


@app.post("/api/admin/set-password/{user_id}")
def admin_set_password(user_id: int, data: AdminSetPasswordRequest, current_client: int = Depends(require_admin), db: Session = Depends(get_db)):
    """Permet à un administrateur de définir un nouveau mot de passe utilisateur."""
    user = db.query(Client).filter(Client.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if not data.new_password or len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractères")

    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = datetime.now()
    db.commit()

    return {
        "status": "ok",
        "message": f"Mot de passe mis à jour pour {user.username}",
        "user_id": user.id,
    }


@app.post("/api/admin/test-welcome-email/{user_id}")
def admin_test_welcome_email(user_id: int, data: AdminWelcomeEmailTestRequest, current_client: int = Depends(require_admin), db: Session = Depends(get_db)):
    """Envoie un email de bienvenue de test vers une boîte cible (ou SMTP_USER par défaut)."""
    user = db.query(Client).filter(Client.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    plan_limits = PLAN_LIMITS.get(user.plan or "free", PLAN_LIMITS["free"])

    test_target = (data.to_email or os.getenv("SMTP_USER") or os.getenv("SENDER_EMAIL") or user.email or "").strip()
    if not test_target:
        raise HTTPException(status_code=400, detail="Aucune adresse email cible disponible")

    # Mot de passe indicatif uniquement pour le mail de test
    temp_password_for_email = "123abc123"

    ok = send_welcome_email(
        to_email=test_target,
        username=user.username,
        temp_password=temp_password_for_email,
        company_name=user.company_name or "Votre Entreprise",
        plan=user.plan or "free",
        limits=plan_limits,
        trial_expires_at=user.trial_expires_at,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Echec envoi email de test")

    return {
        "status": "ok",
        "message": "Email de bienvenue de test envoyé",
        "to_email": test_target,
        "user_id": user.id,
    }


@app.get("/api/admin/all-connections")
def get_all_connections(
    limit: int = Query(default=100, ge=1, le=500),
    grouped: bool = Query(default=True),
    current_client: int = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retourne l'historique de connexions de TOUS les utilisateurs.

    Par défaut, les connexions sont regroupées par appareil/IP pour éviter les doublons.
    """
    fetch_limit = min(max(limit * 10, 300), 3000) if grouped else limit
    rows = (
        db.query(ConnectionLog, Client)
        .outerjoin(Client, ConnectionLog.client_id == Client.id)
        .order_by(ConnectionLog.timestamp.desc())
        .limit(fetch_limit)
        .all()
    )

    if not grouped:
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

    grouped_rows = {}
    for l, client in rows:
        key = (
            l.client_id,
            l.ip_address or "",
            l.browser or "",
            l.os_info or "",
            l.device_type or "",
        )

        if key not in grouped_rows:
            grouped_rows[key] = {
                "id": l.id,
                "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                "first_seen": l.timestamp.isoformat() if l.timestamp else None,
                "last_seen": l.timestamp.isoformat() if l.timestamp else None,
                "session_count": 1,
                "username": client.username if client else "?",
                "company_name": client.company_name if client else "?",
                "ip_address": l.ip_address,
                "location": l.location or "",
                "device_type": l.device_type,
                "browser": l.browser,
                "os_info": l.os_info,
                "user_agent": l.user_agent,
            }
        else:
            grouped_rows[key]["session_count"] += 1
            if l.timestamp and grouped_rows[key]["first_seen"]:
                if l.timestamp.isoformat() < grouped_rows[key]["first_seen"]:
                    grouped_rows[key]["first_seen"] = l.timestamp.isoformat()

    result = sorted(
        grouped_rows.values(),
        key=lambda x: x["timestamp"] or "",
        reverse=True,
    )
    return result[:limit]


# ============ ROUTES FRONTEND ============

@app.get("/manifest.json")
async def get_manifest():
    """Sert le manifest PWA."""
    manifest_path = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'manifest.json'
    )
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return JSONResponse(
                content=_json_push.load(f),
                media_type="application/manifest+json"
            )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="manifest.json non trouvé"
        )


@app.get("/service-worker.js")
async def get_service_worker():
    """Sert le Service Worker."""
    sw_path = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'service-worker.js'
    )
    return FileResponse(
        sw_path,
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache"
        }
    )

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


@app.post("/api/push/subscribe")
async def push_subscribe(
    data: PushSubscriptionModel,
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Enregistre ou met à jour une souscription push.
    Appelé depuis le frontend après demande permission.
    """
    try:
        endpoint = data.endpoint or ""
        keys = data.keys or {}
        client_id = current_client

        if not endpoint or not keys:
            raise HTTPException(
                status_code=400,
                detail="endpoint et keys requis"
            )

        existing = db.query(PushSubscription).filter(
            PushSubscription.endpoint == endpoint
        ).first()

        if existing:
            existing.client_id = client_id
            existing.keys_p256dh = keys.get(
                "p256dh", ""
            )
            existing.keys_auth = keys.get("auth", "")
        else:
            sub = PushSubscription(
                client_id=client_id,
                endpoint=endpoint,
                keys_p256dh=keys.get("p256dh", ""),
                keys_auth=keys.get("auth", "")
            )
            db.add(sub)

        db.commit()
        print(f"[PUSH] Souscription enregistrée client {client_id}")
        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[PUSH] Erreur souscription: {e}")
        raise HTTPException(
            status_code=500, detail=str(e)
        )


@app.post("/api/push/unsubscribe")
async def push_unsubscribe(
    data: dict,
    current_client: int = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Supprime une souscription push."""
    try:
        endpoint = data.get("endpoint", "")
        db.query(PushSubscription).filter(
            PushSubscription.endpoint == endpoint,
            PushSubscription.client_id == current_client,
        ).delete()
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=str(e)
        )


@app.get("/api/push/vapid-public-key")
async def get_vapid_public_key():
    """
    Retourne la clé publique VAPID.
    Utilisée par le frontend pour s'abonner.
    """
    key = os.getenv("VAPID_PUBLIC_KEY", "")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="VAPID non configuré"
        )
    return {"public_key": key}


@app.head("/")
async def head_root():
    """FIX: Répond aux HEAD requests pour health checks UptimeRobot/Render"""
    return Response(status_code=200)


@app.get("/health")
def health():
    """Vérification de l'état de l'application"""
    db_ready = bool(getattr(app.state, "db_ready", False))
    return {
        "status": "ok" if db_ready else "degraded",
        "database": "up" if db_ready else "down",
    }


@app.get("/api/health/detailed")
def health_detailed(request: Request, db: Session = Depends(get_db)):
    """Expose un diagnostic rapide DB/API/clé email pour les tests de robustesse."""
    if not DIAGNOSTICS_PUBLIC:
        raise HTTPException(status_code=404, detail="Not found")
    _verify_service_secret(request)

    results = {}

    try:
        start = time.time()
        db.execute(text("SELECT 1"))
        results["db"] = {
            "status": "ok",
            "latency_ms": round((time.time() - start) * 1000),
        }
    except Exception:
        results["db"] = {"status": "error"}

    try:
        start = time.time()
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast?latitude=49.37&longitude=2.75&current_weather=true",
            timeout=5,
        )
        results["open_meteo"] = {
            "status": "ok" if response.status_code == 200 else "error",
            "latency_ms": round((time.time() - start) * 1000),
        }
    except Exception:
        results["open_meteo"] = {"status": "timeout"}

    tomtom_key = os.getenv("TOMTOM_API_KEY", "")
    brevo_key = os.getenv("BREVO_API_KEY", "")
    results["tomtom"] = {"status": "configured" if tomtom_key else "missing_key"}
    results["brevo"] = {"status": "configured" if brevo_key else "missing_key"}
    results["workers"] = {"status": "configured", "web_concurrency": os.getenv("WEB_CONCURRENCY", "1")}

    overall = "ok" if all(
        check.get("status") in ("ok", "configured")
        for check in results.values()
    ) else "degraded"

    return {"overall": overall, "checks": results}


@app.get("/api/diagnostics")
def diagnostics(request: Request, db: Session = Depends(get_db)):
    """Endpoint diagnostique pour tester la connexion BD et détecter les erreurs."""
    if not DIAGNOSTICS_PUBLIC:
        raise HTTPException(status_code=404, detail="Not found")
    _verify_service_secret(request)

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
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error_message": "internal_error"
        }


@app.post("/api/frontend/error")
async def frontend_error(report: FrontendErrorReport, request: Request):
    """Collecte minimale des erreurs frontend pour accélérer le debug en prod."""
    client_id = None
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth.replace("Bearer ", "", 1)
        try:
            payload = verify_token(token)
            client_id = payload.get("client_id")
        except Exception:
            client_id = None

    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    msg = (report.message or "")[:250]
    src = (report.source or "")[:180]
    page = (report.page_url or "")[:180]
    print(
        f"[FRONTEND-ERROR] kind={report.kind} client={client_id} ip={ip} "
        f"line={report.line}:{report.column} msg={msg} src={src} page={page}"
    )
    if report.stack:
        print(f"[FRONTEND-STACK] {report.stack[:500]}")

    return {"status": "ok"}


@app.head("/health")
async def head_health():
    """FIX: Répond aux HEAD requests health check"""
    return Response(status_code=200)


# ============ LANCEMENT ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
