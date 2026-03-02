from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import candidate_collection
from schemas.candidate import CandidateCreate
from verify.token import verify_access_token
from verify.candidate import verify_candidate_payload


security = HTTPBearer()

router = APIRouter(
    prefix="/candidate",
    tags=["Candidate"]
)



@router.patch("/register")
def register_candidate(
    candidate_data: CandidateCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):


    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)
    if len(candidate)>4:
        raise HTTPException(status_code=404, detail="Candidate Already Registered")

    update_data = candidate_data.model_dump(mode="json")

    update_data["total_resumes"] = 0
    update_data["total_githubs"] = 0
    update_data["total_codings"] = 0
    update_data["total_concepts"] = 0

    if email != update_data["email"].lower():
        raise HTTPException(
            status_code=400,
            detail="Email mismatch"
        )
    

    candidate_collection.update_one(
        {"_id": candidate_id},
        {"$set": update_data}
    )

    return {
        "success": True,
        "message": "Candidate registered successfully"
    }



@router.patch("/change-details")
def change_candidate_details(
    candidate_data: CandidateCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)


    update_data = candidate_data.model_dump(mode="json")

    if email != update_data["email"].lower():
        raise HTTPException(
            status_code=400,
            detail="Email mismatch"
        )

    candidate_collection.update_one(
        {"_id": candidate_id},
        {"$set": update_data}
    )

    return {
        "success": True,
        "message": "Candidate details updated successfully"
    }



@router.get("/profile")
def get_candidate_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)


    candidate["_id"] = str(candidate["_id"])

    return {
        "success": True,
        "data": candidate
    }