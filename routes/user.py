from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from database import user_collection
from schemas.user import UserCreate
from utils.time import IST
from verify.token import verify_access_token
from verify.user import verify_user_payload
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


security = HTTPBearer()

router = APIRouter(prefix="/users", tags=["Users"])




@router.patch("/register")
def signup_user(
    user_data: UserCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
    ):

    token = credentials.credentials
    payload = verify_access_token(token)
    user,user_id ,email = verify_user_payload(payload)
    if len(user)>4:
        raise HTTPException(status_code=404, detail="User Already Registered")

    
    
    update_data = user_data.model_dump(mode="json")

    if email != update_data["email"].lower():
        raise HTTPException(status_code=404, detail="Email Mismatch found")

    user_collection = user_collection()
    user_collection.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )

    return {"message": "User registered successfully"}











@router.patch("/change-details")
def signup_user(
    user_data: UserCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
    ):

    token = credentials.credentials
    payload = verify_access_token(token)
    user,user_id ,email = verify_user_payload(payload)
    
    
    update_data = user_data.model_dump(mode="json")

    if email != update_data["email"].lower():
        raise HTTPException(status_code=404, detail="Email Mismatch found")

    user_collection = user_collection()
    user_collection.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )

    return {"message": "User details changed successfully"}


