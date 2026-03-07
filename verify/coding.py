from fastapi import HTTPException, status
from bson import ObjectId
from bson.errors import InvalidId
from typing import Tuple
from database import leetcode, coding_collection, coding_question_collection
from datetime import datetime, timezone, timedelta
from utils.time import generate_timestamp


def verify_coding(
    coding_id: str,
    candidate_id: ObjectId
) -> Tuple[dict, ObjectId]:

    try:
        coding_obj_id = ObjectId(coding_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid coding_id"
        )

    coding_doc = coding_collection.find_one({
        "_id": coding_obj_id,
        "candidate_id": candidate_id
    })

    if not coding_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coding document not found"
        )

    return (coding_doc, coding_obj_id)

def verify_quantity(
    num_question: int,
    coding_doc: dict
):
    if num_question <= 0:
        raise HTTPException(
            status_code=400,
            detail="Number of questions must be greater than 0."
        )

    available = coding_doc.get("available_ques", 0)

    if num_question > available:
        raise HTTPException(
            status_code=400,
            detail=f"Requested {num_question} questions but only {available} available."
        )
    

def verify_question_session(
    question_session_id: str,
    coding_id: ObjectId
) -> Tuple[dict, ObjectId]:

    try:
        session_obj_id = ObjectId(question_session_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question_session_id"
        )

    session_doc = coding_question_collection.find_one({
        "_id": session_obj_id,
        "coding_id": coding_id
    })

    if not session_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question session not found"
        )

    return session_doc, session_obj_id


def verify_question_id(
    session_doc: dict,
    question_id: int
):
    question_bank = session_doc.get("question_bank", [])

    valid_ids = [q.get("question_id") for q in question_bank]

    if question_id not in valid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question_id"
        )

    return question_id


def verify_session_status(session_doc: dict):

    if session_doc.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active"
        )
     
def verify_session_status2(session_doc: dict):

    if session_doc.get("status") != "passive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not passive"
        )




def verify_session_time(session_doc: dict, session_obj_id: ObjectId):

    start_time = session_doc["timestamp"]
    total_time = session_doc["time"]

    now = generate_timestamp()
    elapsed_minutes = (now - start_time).total_seconds() / 60

    if elapsed_minutes > total_time:

        coding_question_collection.update_one(
            {"_id": session_obj_id},
            {"$set": {"status": "passive"}}
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session time expired"
        )







def verify_timestamp(frontend_time):
    try:
        if frontend_time.tzinfo is not None:
            frontend_time = frontend_time.astimezone(timezone.utc)
        else:
            frontend_time = frontend_time.replace(tzinfo=timezone.utc)

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid frontend timestamp format"
        )
    
    backend_time = generate_timestamp()


    time_diff_seconds = abs((backend_time - frontend_time).total_seconds())

    if time_diff_seconds > 120:
        raise HTTPException(
            status_code=400,
            detail="Submission time mismatch exceeds 2 minutes"
        )
    
    return frontend_time, backend_time






