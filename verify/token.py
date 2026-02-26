from fastapi import HTTPException, status
from google.oauth2 import id_token
from google.auth.transport import requests
from jose import jwt, JWTError
from utils.reader import GOOGLE_CLIENT_ID, JWT_SECRET, JWT_ALGO



def verify_google_token(data: dict|None) -> dict:

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid input")


    token = data.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Token missing")
    
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        return idinfo

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )


def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGO]
        )

        if payload.get("exp") is None:
            raise HTTPException(status_code=401, detail="Token has no expiry")

        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )


def create_access_token(payload: dict) -> str:

    token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGO
    )

    return token