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

# Configuration base de données (PostgreSQL sur Render, SQLite en local)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./meteo_saas.db"
)

# Render fournit postgres:// mais SQLAlchemy
# requiert postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql://", 1
    )

if "postgresql" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300
    )
else:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
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
    is_admin = Column(Integer, default=0)  # 1 = administrateur
    zone_changes = Column(Integer, default=0)  # compteur de changements de zones

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


class PrevisionCache(Base):
    """Table previsions_cache : prévisions J+5 envoyées par GitHub Actions"""
    __tablename__ = "previsions_cache"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), index=True)
    jour = Column(String)        # "Mar 01/04"
    tmin = Column(String)        # "5.2°C"
    tmax = Column(String)        # "12.1°C"
    pluie = Column(String)       # "2.3 mm"
    uv = Column(Float)
    risques = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow)

    zone = relationship("Zone")


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


class ConnectionLog(Base):
    """Table connection_logs : historique des connexions"""
    __tablename__ = "connection_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    device_type = Column(String, nullable=True)  # "desktop", "mobile", "tablet"
    browser = Column(String, nullable=True)
    os_info = Column(String, nullable=True)
    location = Column(String, nullable=True)  # "Paris, FR"

    client = relationship("Client")


# ============ FONCTIONS D'INITIALISATION ============

def init_db():
    """Crée les tables et applique les migrations"""
    Base.metadata.create_all(bind=engine)
    print("✅ Bases de données initialisées")
    
    # Migration: ajouter les colonnes météo manquantes à la table zones
    try:
        from sqlalchemy import text
        db = SessionLocal()
        
        # Vérifier si les colonnes manquent et les ajouter
        columns_to_add = [
            ("precipitation", "REAL"),
            ("cloudcover", "REAL"),
            ("uv_index", "REAL")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                # Essayer d'ajouter la colonne
                db.execute(text(f"ALTER TABLE zones ADD COLUMN {col_name} {col_type}"))
                db.commit()
                print(f"  ✅ Colonne {col_name} ajoutée")
            except Exception as e:
                # La colonne existe déjà, c'est normal
                db.rollback()
        
        # Migration: ajouter zone_changes à la table clients
        try:
            db.execute(text("ALTER TABLE clients ADD COLUMN zone_changes INTEGER DEFAULT 0"))
            db.commit()
            print("  ✅ Colonne zone_changes ajoutée à clients")
        except Exception:
            db.rollback()
        
        # Migration: mettre à jour le mot de passe des clients JSON depuis INIT_CLIENT_PASSWORD
        init_password = os.getenv("INIT_CLIENT_PASSWORD")
        if init_password:
            from passlib.context import CryptContext
            pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            # Mettre à jour geodis-lemeux si le client existe
            client = db.query(Client).filter(Client.username == "geodis-lemeux").first()
            if client:
                client.password_hash = pwd_ctx.hash(init_password)
                db.commit()
                print("  ✅ Mot de passe geodis-lemeux mis à jour depuis INIT_CLIENT_PASSWORD")
        
        # Migration: contrainte unique (client_id, zone_name) pour éviter les doublons
        try:
            db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uix_client_zone ON zones (client_id, name)"))
            db.commit()
            print("  ✅ Contrainte unique (client_id, zone_name) ajoutée")
        except Exception:
            db.rollback()

        # Migration: ajouter colonne location à connection_logs
        try:
            db.execute(text("ALTER TABLE connection_logs ADD COLUMN location VARCHAR"))
            db.commit()
            print("  ✅ Colonne location ajoutée à connection_logs")
        except Exception:
            db.rollback()

        # Migration: ajouter colonne is_admin à clients
        try:
            db.execute(text("ALTER TABLE clients ADD COLUMN is_admin INTEGER DEFAULT 0"))
            db.commit()
            print("  ✅ Colonne is_admin ajoutée à clients")
        except Exception:
            db.rollback()

        # S'assurer que le premier client (geodis-lemeux) est admin
        try:
            db.execute(text("UPDATE clients SET is_admin = 1 WHERE id = 1"))
            db.commit()
        except Exception:
            db.rollback()
        
        db.close()
    except Exception as e:
        print(f"  ⚠️ Migration: {e}")


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
                # Mettre à jour le plan si différent
                new_plan = client_dict.get("plan", "free")
                if existing.plan != new_plan:
                    existing.plan = new_plan
                    db.commit()
                    print(f"✅ Plan mis à jour pour {client_dict['username']}: {new_plan}")
                # Sync zones manquantes pour le client existant
                zones_data = client_dict.get("zones", {})
                added = 0
                for zone_type, zone_key in [("site", "sites"), ("voisin", "voisins")]:
                    for z in zones_data.get(zone_key, []):
                        zone_exists = db.query(Zone).filter(
                            Zone.client_id == existing.id,
                            Zone.name == z["name"]
                        ).first()
                        if not zone_exists:
                            db.add(Zone(
                                client_id=existing.id,
                                name=z["name"],
                                lat=z["lat"],
                                lon=z["lon"],
                                type=zone_type
                            ))
                            added += 1
                if added:
                    db.commit()
                    print(f"✅ {added} zone(s) ajoutée(s) pour {client_dict['username']}")
                else:
                    print(f"⚠️ Client {client_dict['username']} existe déjà (zones à jour)")
                continue

            # Créer le client
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            # Mot de passe : depuis le JSON, la variable d'env, ou un défaut sécurisé
            raw_password = client_dict.get("password") or os.getenv("INIT_CLIENT_PASSWORD")
            if not raw_password:
                print(f"⚠️ Pas de mot de passe pour {client_dict['username']} — client ignoré")
                continue
            
            client = Client(
                username=client_dict["username"],
                password_hash=pwd_context.hash(raw_password),
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
                # CORRECTION: Vérifier si la zone existe déjà pour éviter les doublons
                zone_existante = db.query(Zone).filter(
                    Zone.client_id == client.id,
                    Zone.name == site["name"]
                ).first()
                
                if not zone_existante:
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
                # CORRECTION: Vérifier si la zone existe déjà pour éviter les doublons
                zone_existante = db.query(Zone).filter(
                    Zone.client_id == client.id,
                    Zone.name == voisin["name"]
                ).first()
                
                if not zone_existante:
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
