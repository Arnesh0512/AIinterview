from fastapi import HTTPException, status
from bson import ObjectId
from bson.errors import InvalidId
from typing import Tuple
from database import resume_collection, resume_question_collection, resume_fs
from datetime import datetime, timezone


def verify_resume(
    resume_id: str,
    candidate_id: ObjectId
) -> Tuple[dict, ObjectId]:

    try:
        resume_obj_id = ObjectId(resume_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resume_id"
        )

    resume_doc = resume_collection.find_one({
        "_id": resume_obj_id,
        "candidate_id": candidate_id
    })

    if not resume_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume document not found"
        )

    return (resume_doc, resume_obj_id)

def verify_question_session(
    question_session_id: str,
    resume_id: ObjectId
) -> Tuple[dict, ObjectId]:

    try:
        session_obj_id = ObjectId(question_session_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question_session_id"
        )

    session_doc = resume_question_collection.find_one({
        "_id": session_obj_id,
        "resume_id": resume_id
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

    now = datetime.now(timezone.utc)
    elapsed_minutes = (now - start_time).total_seconds() / 60

    if elapsed_minutes > total_time:

        resume_question_collection.update_one(
            {"_id": session_obj_id},
            {"$set": {"status": "passive"}}
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session time expired"
        )





def verify_file_id(file_id: str):

    try:
        file_obj_id = ObjectId(file_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file_id"
        )
    if not resume_fs.exists(file_obj_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    return file_obj_id
    
