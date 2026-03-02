from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from jose import jwt
from database import candidate_collection
from utils.reader import JWT_ALGO, JWT_SECRET
from datetime import datetime, date

router = APIRouter(prefix="/dev", tags=["Dev Auth"])


SECRET_KEY = JWT_SECRET
ALGORITHM = JWT_ALGO
ACCESS_TOKEN_EXPIRE_MINUTES = 600000



def create_access_token(payload: dict) -> str:

    token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGO
    )

    return token


# =====================================================
# TEMP LOGIN ROUTE (FOR DEVELOPMENT ONLY)
# =====================================================
@router.post("/generate-token")
def generate_token(email: str):

    candidate = candidate_collection.find_one({"email": email.lower()})

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate_id = str(candidate["_id"])

    today=date.today()
    access_token = create_access_token(    payload = {
        "candidate_id":candidate_id,
        "email": email,
        "role": "candidate",
        "exp": datetime(today.year + (1 if today.month > 6 else 0),6,30, 18,30)
    }
    )

    return {access_token}