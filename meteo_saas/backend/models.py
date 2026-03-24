# -*- coding: utf-8 -*-
"""
models.py — Schémas Pydantic pour validation et sérialisation
"""

from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


# ============ AUTHENTIFICATION ============

class LoginRequest(BaseModel):
    """Requête pour la connexion"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Réponse contenant le token JWT"""
    access_token: str
    token_type: str
    client_id: int
    company_name: str


# ============ MÉTÉO ============

class ZoneMeteo(BaseModel):
    """Données météo actuelles d'une zone"""
    name: str
    type: str  # "site" ou "voisin"
    temp: Optional[float] = None
    wind: Optional[float] = None
    direction: Optional[str] = None
    ciel: Optional[str] = None
    risques: Optional[str] = None
    precipitation: Optional[float] = None
    cloudcover: Optional[float] = None
    uv_index: Optional[float] = None
    lat: float
    lon: float
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PrevisionJour(BaseModel):
    """Prévision météo pour un jour"""
    zone: str
    jour: str  # "Mon 19/03" format
    tmin: Optional[str] = None
    tmax: Optional[str] = None
    pluie: Optional[str] = None
    uv: Optional[float] = None
    risques: Optional[str] = None


class Alerte(BaseModel):
    """Alerte météo"""
    zone_name: str
    timestamp: datetime
    type_alerte: str  # "verglas", "vent_fort", "pluie", "uv"
    valeur: str
    message: str

    class Config:
        from_attributes = True


# ============ TRAFIC ============

class TrafficIncident(BaseModel):
    """Incident trafic"""
    route: str
    description: str
    severity: str  # "low", "med", "high"
    delay_minutes: int
    lat: float
    lon: float
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ ZONES ============

class ZoneInfo(BaseModel):
    """Informations d'une zone"""
    id: int
    name: str
    lat: float
    lon: float
    type: str

    class Config:
        from_attributes = True
