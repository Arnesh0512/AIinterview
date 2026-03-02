from fastapi import HTTPException, status
from database import candidate_collection
from bson import ObjectId
from bson.errors import InvalidId
from typing import Tuple

def verify_candidate_payload(payload: dict) -> Tuple[dict|None, ObjectId, str]:

    candidate_id = payload.get("candidate_id")
    email = payload.get("email")
    role = payload.get("role")

    if not candidate_id or not email or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    if role != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a candidate"
        )
    
    return verify_candidate(candidate_id, email, "Y")







def verify_candidate(candidate_id: str, email: str, type:str) -> Tuple[dict|None, ObjectId, str]:

    email = email.lower()

    try:
        candidate_obj_id = ObjectId(candidate_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid candidate id"
        )
    print(candidate_id,email)

    
    candidate = candidate_collection.find_one({
        "_id": candidate_obj_id,
        "email": email
    })

    if type == "N":
        if candidate:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="candidate Already exists"
        )

    if type == "Y":
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="candidate not found"
            )
        

    return (candidate,candidate_obj_id,email)




def verify_candidate_by_email(email: str, type: str) -> Tuple[dict|None, ObjectId|None, str]:
    email = email.lower()

    
    candidate = candidate_collection.find_one({
        "email": email
    })

    if type == "N":
        if candidate:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="candidate Already exists"
        )
        candidate_obj_id = None


    if type == "Y":
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="candidate not found"
            )
        candidate_obj_id = candidate["_id"]

    return (candidate,candidate_obj_id,email)



def verify_candidate_by_id(candidate_id: str, type: str) -> Tuple[dict|None, ObjectId, str|None]:

    try:
        candidate_obj_id = ObjectId(candidate_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid candidate id"
        )

    
    candidate = candidate_collection.find_one({
        "_id": candidate_obj_id,
    })

    if type == "N":
        if candidate:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="candidate Already exists"
        )
        email = None

    if type == "Y":
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="candidate not found"
            )
        email=candidate["email"]
        
    return (candidate,candidate_obj_id,email)