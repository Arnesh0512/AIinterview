from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId
from database import user_collection
from schemas.user import UserCreate

router = APIRouter(prefix="/users", tags=["Users"])


@router.patch("/register")
def signup_user(
    user_id: str,
    user_data: UserCreate
):
    try:
        user_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = user_collection.find_one({"_id": user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.get("email"):  # already registered
        raise HTTPException(status_code=400, detail="User Already Registered")

    update_data = user_data.model_dump(mode="json")

    if update_data["email"].lower() != update_data["email"]:
        raise HTTPException(status_code=400, detail="Email must be lowercase")

    user_collection.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )

    return {"message": "User registered successfully"}


@router.patch("/change-details")
def change_user_details(
    user_id: str,
    user_data: UserCreate
):
    try:
        user_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = user_collection.find_one({"_id": user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_data.model_dump(mode="json")

    if user.get("email") != update_data["email"].lower():
        raise HTTPException(status_code=400, detail="Email mismatch")

    user_collection.update_one(
        {"_id": user_id},
        {"$set": update_data}
    )

    return {"message": "User details changed successfully"}