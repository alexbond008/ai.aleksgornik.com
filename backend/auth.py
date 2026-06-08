"""
Email-gate auth: POST name+email → subscribe to Kit.com → return JWT session token.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from jose import JWTError, jwt

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

KIT_API_KEY = os.getenv("KIT_API_KEY")
KIT_FORM_ID = os.getenv("KIT_FORM_ID")


def create_token(user_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


async def subscribe_to_kit(name: str, email: str) -> bool:
    """Subscribe email to Kit.com form. Returns True on success."""
    if not KIT_API_KEY or not KIT_FORM_ID:
        # Dev mode: skip Kit subscription
        return True

    url = f"https://api.convertkit.com/v3/forms/{KIT_FORM_ID}/subscribe"
    payload = {
        "api_key": KIT_API_KEY,
        "email": email,
        "first_name": name,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
        except httpx.RequestError:
            return False
