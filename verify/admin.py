from fastapi import HTTPException, status
from database import admin_collection, contest_collection
from bson import ObjectId
from bson.errors import InvalidId
from typing import Tuple
from schemas.contest import ContestCreate

def verify_admin_payload(payload: dict) -> Tuple[dict|None, ObjectId, str]:

    admin_id = payload.get("admin_id")
    email = payload.get("email")
    role = payload.get("role")

    if not admin_id or not email or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a admin"
        )
    
    return verify_admin(admin_id, email, "Y")




def verify_admin(admin_id: str, email: str, type:str) -> Tuple[dict|None, ObjectId, str]:

    email = email.lower()

    try:
        admin_obj_id = ObjectId(admin_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin id"
        )

    admin = admin_collection.find_one({
        "_id": admin_obj_id,
        "email": email
    })

    if type == "N":
        if admin:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin Already exists"
        )

    if type == "Y":
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        

    return (admin,admin_obj_id,email)





def verify_admin_by_email(email: str, type: str) -> Tuple[dict|None, ObjectId|None, str]:
    email = email.lower()

    admin = admin_collection.find_one({
        "email": email
    })

    if type == "N":
        if admin:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin Already exists"
        )
        admin_obj_id = None


    if type == "Y":
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        admin_obj_id = admin["_id"]

    return (admin,admin_obj_id,email)



def verify_admin_by_id(admin_id: str, type: str) -> Tuple[dict|None, ObjectId, str|None]:

    try:
        admin_obj_id = ObjectId(admin_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin id"
        )

    admin = admin_collection.find_one({
        "_id": admin_obj_id,
    })

    if type == "N":
        if admin:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin Already exists"
        )
        email = None

    if type == "Y":
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        email=admin["email"]
        
    return (admin,admin_obj_id,email)






from fastapi import HTTPException
from database import contest_collection


from datetime import timedelta



def verify_duplicate_contest(data: ContestCreate):

    data = data.model_dump()


    existing = contest_collection.find_one({

        "company": data["company"],
        "role": data["role"],
        "skills": sorted(data["skills"]),
        "candidate_capacity": data["candidate_capacity"],

        "last_date_to_register": data["last_date_to_register"],
        "contest_start": data["contest_start"],

        "resume_round.start": data["resume_round"]["start"],
        "coding_round.start": data["coding_round"]["start"],
        "concept_round.start": data["concept_round"]["start"],
        "hr_round.start": data["hr_round"]["start"]
    })

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Contest with same configuration already exists"
        )

    return True






def validate_contest_data(data: ContestCreate):

    last_date_to_register = data.last_date_to_register
    contest_start = data.contest_start
    contest_end = data.contest_end
    leaderboard_time = data.leaderboard_declare_time

    resume_start = data.resume_round.start
    resume_end = data.resume_round.end
    resume_duration = data.resume_round.duration
    resume_result_time = data.resume_round.result

    coding_start = data.coding_round.start
    coding_end = data.coding_round.end
    coding_duration = data.coding_round.duration
    coding_result_time = data.coding_round.result

    concept_start = data.concept_round.start
    concept_end = data.concept_round.end
    concept_duration = data.concept_round.duration
    concept_result_time = data.concept_round.result

    hr_start = data.hr_round.start
    hr_end = data.hr_round.end
    hr_duration = data.hr_round.duration
    hr_result_time = data.hr_round.result

    candidate_capacity = data.candidate_capacity

    selected_resume = data.selected_resume
    selected_coding = data.selected_coding
    selected_concept = data.selected_concept
    selected_hr = data.selected_hr




    if not (
        last_date_to_register < 
        resume_start < resume_end < 
        contest_start < resume_result_time <
        coding_start < coding_end < coding_result_time <
        concept_start < concept_end < concept_result_time <
        hr_start < hr_end < hr_result_time <
        contest_end < 
        leaderboard_time
    ):
        raise HTTPException(
            status_code=400,
            detail="Time sequence invalid"
        )
    
    if not (
        selected_hr <= selected_concept <=
        selected_coding <= selected_resume <=
        candidate_capacity
    ):
        raise HTTPException(
            status_code=400,
            detail="Selection sequence invalid"
        )
        




    if (resume_end - resume_start).total_seconds() < resume_duration:
        raise HTTPException(
            status_code=400,
            detail="Resume duration invalid"
        )

    if (coding_end - coding_start).total_seconds() < coding_duration:
        raise HTTPException(
            status_code=400,
            detail="Coding duration invalid"
        )

    if (concept_end - concept_start).total_seconds() < concept_duration:
        raise HTTPException(
            status_code=400,
            detail="Concept duration invalid"
        )

    if (hr_end - hr_start).total_seconds() < hr_duration:
        raise HTTPException(
            status_code=400,
            detail="HR duration invalid"
        )
    

    if(data.resume_questions_count < 1 or
       data.coding_questions_count < 1 or
       data.concept_questions_count < 1 or 
       data.hr_questions_count < 2):
        raise HTTPException(
            status_code=400,
            detail="Error in number of questions"
        )
    
    if(resume_duration/60 < data.resume_questions_count or 
       coding_duration/60 < data.coding_questions_count or
       concept_duration/60 < data.concept_questions_count or
       hr_duration/60 < data.hr_questions_count ):
        raise HTTPException(
            status_code=400,
            detail="Not enough time provided."
        )
    






def verify_contest_id(contest_id: str):

    try:
        obj_id = ObjectId(contest_id)
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail="Invalid contest_id"
        )

    contest = contest_collection.find_one({"_id": obj_id})

    if not contest:
        raise HTTPException(
            status_code=404,
            detail="Contest not found"
        )

    return contest, obj_id




