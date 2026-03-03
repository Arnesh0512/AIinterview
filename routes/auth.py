from fastapi import APIRouter
from datetime import datetime, timezone, date
from database import candidate_collection
from verify.token import verify_google_token,create_access_token
from utils.time import generate_timestamp


router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/candidate")
def google_auth_candidate(data: dict):

    idinfo = verify_google_token(data)
    email = idinfo["email"].lower()
    profile_pic = idinfo["picture"],

    candidate = candidate_collection.find_one({"email": email})
    if candidate:
        candidate_id = str(candidate["_id"])
    else:
        result = candidate_collection.insert_one({
            "email": email,
            "profile_pic": profile_pic,
            "created_on": generate_timestamp(),
        })
        candidate_id = str(result.inserted_id)


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

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

