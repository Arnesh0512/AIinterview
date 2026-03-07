from fastapi import HTTPException, status
from bson import ObjectId
from bson.errors import InvalidId
from typing import Tuple
from database import concept_collection, concept_question_collection
from datetime import datetime, timezone, timedelta
from utils.time import generate_timestamp


def verify_concept(
    concept_id: str,
    candidate_id: ObjectId
) -> Tuple[dict, ObjectId]:

    try:
        concept_obj_id = ObjectId(concept_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid concept_id"
        )

    concept_doc = concept_collection.find_one({
        "_id": concept_obj_id,
        "candidate_id": candidate_id
    })

    if not concept_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="concept document not found"
        )

    return (concept_doc, concept_obj_id)





def verify_question_session(
    question_session_id: str,
    concept_id: ObjectId
) -> Tuple[dict, ObjectId]:

    try:
        session_obj_id = ObjectId(question_session_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question_session_id"
        )

    session_doc = concept_question_collection.find_one({
        "_id": session_obj_id,
        "concept_id": concept_id
    })

    if not session_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question session not found"
        )

    return session_doc, session_obj_id




def verify_question_number(
    session_doc: dict,
    question_number: int
):

    question_bank = session_doc.get("question_bank", [])

    if question_number < 1 or question_number > len(question_bank):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question_number"
        )


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

        concept_question_collection.update_one(
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







