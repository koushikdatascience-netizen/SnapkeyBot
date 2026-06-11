import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
passwords = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return passwords.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return passwords.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.jwt_secret, algorithm="HS256")


def create_purpose_token(user_id: uuid.UUID, purpose: str, minutes: int = 15) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode(
        {"sub": str(user_id), "purpose": purpose, "exp": expires},
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_purpose_token(token: str, purpose: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("purpose") != purpose:
            raise ValueError("Invalid token purpose")
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise ValueError("Invalid token") from exc


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("purpose"):
            raise ValueError("Purpose token cannot be used as an access token")
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise ValueError("Invalid token") from exc


def _fernet() -> Fernet:
    if settings.credential_encryption_key:
        key = settings.credential_encryption_key.encode()
    else:
        digest = hashlib.sha256(settings.jwt_secret.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_credentials(credentials: dict) -> str:
    return _fernet().encrypt(json.dumps(credentials).encode()).decode()


def decrypt_credentials(value: str) -> dict:
    return json.loads(_fernet().decrypt(value.encode()).decode()) if value else {}


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        user_id = decode_access_token(token)
    except ValueError:
        raise unauthorized
    user = await db.get(User, user_id)
    if not user:
        raise unauthorized
    return user
