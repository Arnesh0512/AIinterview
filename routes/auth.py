from fastapi import APIRouter
from datetime import datetime, date
from database import user_collection
from utils.time import IST
from verify.token import verify_google_token,create_access_token
from verify.user import verify_user_by_email

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/user")
def google_auth_user(data: dict):

    idinfo = verify_google_token(data)
    email = idinfo["email"].lower()

    user_collection = user_collection()
    user = user_collection.find_one({"email": email})
    if user:
        user_id = str(user["_id"])
    else:
        result = user_collection.insert_one({
            "email": email,
            "created_on": datetime.now(IST).isoformat(),
        })
        user_id = str(result.inserted_id)


    today=date.today()
    payload = {
        "user_id":user_id,
        "email": email,
        "role": "user",
        "exp": datetime(today.year + (1 if today.month > 6 else 0),6,30, 18,30)
    }
    
    access_token = create_access_token(payload)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

