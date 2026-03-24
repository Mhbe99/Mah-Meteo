# -*- coding: utf-8 -*-
"""
database.py — Modèles SQLAlchemy et initialisation SQLite
"""

import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Configuration SQLite
DATABASE_URL = "sqlite:///./meteo_saas.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============ MODÈLES SQLAlchemy ============

class Client(Base):
    """Table clients : gère les comptes utilisateurs"""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    company_name = Column(String)
    email = Column(String)
    plan = Column(String, default="free")  # free, pro, enterprise
    active = Column(Integer, default=1)  # booléen stocké comme 0/1

    # Relations
    zones = relationship("Zone", back_populates="client", cascade="all, delete-orphan")
    alertes_log = relationship("AlerteLog", back_populates="client", cascade="all, delete-orphan")
    trafic_incidents = relationship("TrafficIncident", back_populates="client", cascade="all, delete-orphan")


class Zone(Base):
    """Table zones : zones météo (sites et voisins)"""
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), index=True)
    name = Column(String, index=True)
    lat = Column(Float)
    lon = Column(Float)
    type = Column(String)  # "site" ou "voisin"
    
    # Données météo actuelles (dernière mise à jour)
    temperature = Column(Float, nullable=True)
    windspeed = Column(Float, nullable=True)
    wind_direction = Column(String, nullable=True)
    precipitation = Column(Float, nullable=True)
    cloudcover = Column(Float, nullable=True)
    uv_index = Column(Float, nullable=True)
    risques = Column(Text, nullable=True)
    ciel = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    # Relations
    client = relationship("Client", back_populates="zones")
    meteo_snapshots = relationship("MeteoSnapshot", back_populates="zone", cascade="all, delete-orphan")


class MeteoSnapshot(Base):
    """Table meteo_snapshot : historique des données météo"""
    __tablename__ = "meteo_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    temperature = Column(Float, nullable=True)
    windspeed = Column(Float, nullable=True)
    wind_direction = Column(String, nullable=True)
    precipitation = Column(Float, nullable=True)
    cloudcover = Column(Float, nullable=True)
    uv_index = Column(Float, nullable=True)
    risques = Column(Text, nullable=True)
    ciel = Column(String, nullable=True)

    # Relations
    zone = relationship("Zone", back_populates="meteo_snapshots")


class TrafficIncident(Base):
    """Table trafic_incidents : incidents trafic temps réel"""
    __tablename__ = "trafic_incidents"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    route = Column(String)
    description = Column(Text)
    severity = Column(String)  # "low", "med", "high"
    delay_minutes = Column(Integer, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

    # Relations
    client = relationship("Client", back_populates="trafic_incidents")


class AlerteLog(Base):
    """Table alertes_log : historique des alertes"""
    __tablename__ = "alertes_log"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), index=True)
    zone_name = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    type_alerte = Column(String)  # "verglas", "vent_fort", "pluie", "uv", etc.
    valeur = Column(String)
    message = Column(Text)

    # Relations
    client = relationship("Client", back_populates="alertes_log")


# ============ FONCTIONS D'INITIALISATION ============

def init_db():
    """Crée les tables dans la base de données"""
    Base.metadata.create_all(bind=engine)
    print("✅ Bases de données initialisées")


def init_clients_from_json(json_path):
    """Lit data/clients.json et insère les clients + zones s'ils n'existent pas"""
    if not os.path.exists(json_path):
        print(f"⚠️ Fichier {json_path} introuvable — pas d'initialisation")
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        db = SessionLocal()

        for client_dict in data.get("clients", []):
            # Vérifier si le client existe déjà
            existing = db.query(Client).filter(Client.username == client_dict["username"]).first()
            if existing:
                print(f"⚠️ Client {client_dict['username']} existe déjà")
                continue

            # Créer le client
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            client = Client(
                username=client_dict["username"],
                password_hash=pwd_context.hash(client_dict["password"]),
                company_name=client_dict["company_name"],
                email=client_dict["email"],
                plan=client_dict.get("plan", "free"),
                active=1
            )
            db.add(client)
            db.flush()  # Récupère l'ID généré

            # Ajouter les zones du client
            zones_data = client_dict.get("zones", {})
            
            # Sites
            for site in zones_data.get("sites", []):
                zone = Zone(
                    client_id=client.id,
                    name=site["name"],
                    lat=site["lat"],
                    lon=site["lon"],
                    type="site"
                )
                db.add(zone)

            # Voisins
            for voisin in zones_data.get("voisins", []):
                zone = Zone(
                    client_id=client.id,
                    name=voisin["name"],
                    lat=voisin["lat"],
                    lon=voisin["lon"],
                    type="voisin"
                )
                db.add(zone)

            db.commit()
            print(f"✅ Client {client_dict['username']} créé avec {len(zones_data.get('sites', []))} sites + {len(zones_data.get('voisins', []))} voisins")

        db.close()

    except Exception as e:
        print(f"❌ Erreur initialisation clients : {e}")


def get_db():
    """Dépendance FastAPI pour obtenir une session DB"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
