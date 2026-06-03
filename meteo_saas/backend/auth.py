# -*- coding: utf-8 -*-
"""
auth.py — Authentification JWT et gestion des tokens
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

# Charger variables d'environnement
load_dotenv()

# Clé JWT obligatoire — refuse de démarrer si absente
SECRET_KEY = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")

if not SECRET_KEY:
    print("[SECURITE] ERREUR : JWT_SECRET non défini dans .env")
    print("[SECURITE] Définir JWT_SECRET dans les variables d'environnement")
    sys.exit(1)

if len(SECRET_KEY) < 32:
    print("[SECURITE] AVERTISSEMENT : JWT_SECRET trop court (minimum 32 caractères)")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Context pour hacher les mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============ UTILITAIRES ============

def hash_password(password: str) -> str:
    """Hash un mot de passe avec bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe contre son hash"""
    return pwd_context.verify(plain_password, hashed_password)


# ============ TOKENS JWT ============

def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Crée un JWT avec les données fournies.
    Expire dans 24h par défaut.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Vérifie un token JWT et retourne les données encodées.
    Lève une exception si le token est invalide ou expiré.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============ DÉPENDANCES ============

async def get_current_client(authorization: Optional[str] = Header(None)) -> int:
    """
    Dépendance FastAPI pour extraire et vérifier le client depuis le token JWT dans le header Authorization.
    Retourne le client_id. Vérifie aussi que le client existe et est actif en DB.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant ou format invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.replace("Bearer ", "", 1)
    payload = verify_token(token)
    
    client_id = payload.get("client_id")
    if client_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client ID non trouvé dans le token",
        )

    # Vérifier que le client existe et est actif en DB
    from .database import SessionLocal, Client
    try:
        db = SessionLocal()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de données indisponible",
        )
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client or not client.active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Compte désactivé ou supprimé",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Erreur base de données",
        )
    finally:
        db.close()
    
    return client_id
