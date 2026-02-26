from fastapi import HTTPException, status
from database import user_collection
from bson import ObjectId
from bson.errors import InvalidId
from typing import Tuple

def verify_user_payload(payload: dict) -> Tuple[dict|None, ObjectId, str]:

    user_id = payload.get("user_id")
    email = payload.get("email")
    role = payload.get("role")

    if not user_id or not email or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    if role != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a user"
        )
    
    return verify_user(user_id, email, "Y")







def verify_user(user_id: str, email: str, type:str) -> Tuple[dict|None, ObjectId, str]:

    email = email.lower()

    try:
        user_obj_id = ObjectId(user_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id"
        )

    user_collection = user_collection()
    user = user_collection.find_one({
        "_id": user_obj_id,
        "email": email
    })

    if type == "N":
        if user:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User Already exists"
        )

    if type == "Y":
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        

    return (user,user_obj_id,email)




def verify_user_by_email(email: str, type: str) -> Tuple[dict|None, ObjectId|None, str]:
    email = email.lower()

    user_collection = user_collection()
    user = user_collection.find_one({
        "email": email
    })

    if type == "N":
        if user:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User Already exists"
        )
        user_obj_id = None


    if type == "Y":
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user_obj_id = user["_id"]

    return (user,user_obj_id,email)



def verify_user_by_id(user_id: str, type: str) -> Tuple[dict|None, ObjectId, str|None]:

    try:
        user_obj_id = ObjectId(user_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id"
        )

    user_collection = user_collection()
    user = user_collection.find_one({
        "_id": user_obj_id,
    })

    if type == "N":
        if user:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User Already exists"
        )
        email = None

    if type == "Y":
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        email=user["email"]
        
    return (user,user_obj_id,email)