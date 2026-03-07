from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta, timezone
from jose import jwt
from database import candidate_collection, admin_collection
from utils.reader import JWT_ALGO, JWT_SECRET
from datetime import datetime, date
from verify.token import create_access_token

router = APIRouter(prefix="/dev", tags=["Dev Auth"])



@router.post("/generate-candidate-token")
def generate_token(email: str):

    candidate = candidate_collection.find_one({"email": email.lower()})

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate_id = str(candidate["_id"])

    today=date.today()
    Year = today.year + (1 if today.month > 6 else 0)
    Month = 6
    Date = 30



    payload = {
        "candidate_id":candidate_id,
        "email": email,
        "role": "candidate",
        "exp": datetime(Year, Month, Date , 18,30, tzinfo=timezone.utc)
    }


    access_token = create_access_token(payload)

    return {access_token}





@router.post("/generate-admin-token")
def generate_token(email: str):

    admin = admin_collection.find_one({"email": email.lower()})

    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    admin_id = str(admin["_id"])

    today=date.today()
    Year = today.year + (1 if today.month > 6 else 0)
    Month = 6
    Date = 30


    payload = {
        "admin_id":str(admin_id),
        "email": email,
        "role": "admin",
        "exp": datetime(Year, Month, Date , 18,30, tzinfo=timezone.utc)
    }
    
    access_token = create_access_token(payload)

    return {access_token}