from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import concept_collection, concept_question_collection, candidate_collection
from verify.token import verify_access_token
from verify.candidate import verify_candidate_payload
from constants.topic import TopicEnum
from typing import List
from verify.concept import verify_concept, verify_question_number, verify_question_session, verify_session_status,verify_session_status2, verify_session_time, verify_timestamp
from prompt.concept import generate_concept_topic_questions, evaluate_concept_topic_answers, generate_concept_combined_diff_session_feedback, generate_concept_combined_same_session_feedback
from utils.concept import previous_concept_session_questions, auto_submit
from utils.time import generate_timestamp
import asyncio

router = APIRouter(prefix="/concept", tags=["Conceptual"])
security = HTTPBearer()


@router.post("/start")
def start_concept(
    topic: List[TopicEnum],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    if not topic:
        raise HTTPException(
            status_code=400,
            detail="At least one topic must be selected"
        )

    concept_doc = {
    "candidate_id": candidate_id,
    "concept_number": candidate["total_concepts"]+1,
    "topic": [t.value for t in topic] if topic else [],
    "created_on": generate_timestamp(),
    "total_sessions":0
    }
    
    result = concept_collection.insert_one(concept_doc)

    candidate_collection.update_one(
        {"_id": candidate_id},
        {
            "$inc": {
                "total_concepts": 1
            }
        }
    )

    return {
        "success": True
    }



@router.get("/all")
def get_all_concept_ids(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concepts = concept_collection.find(
        {"candidate_id": candidate_id},
        {"_id": 1,"topic":1, "created_on":1}
    ).sort("created_on", -1)

    concept_list = [
        {
            "concept_id": str(doc["_id"]),
            "concept_number": doc.get("concept_number"),
            "topic": doc.get("topic", []),
            "created_on": doc.get("created_on")
        }
        for doc in concepts
    ]

    return {
        "success": True,
        "concepts": concept_list
    }




@router.post("/questions/submit")
def submit_session(
    concept_id: str,
    question_session_id: str,
    frontend_timestamp: datetime,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        concept_obj_id
    )

    verify_session_status(session_doc)
    verify_session_time(session_doc, session_obj_id)
    frontend_time , backend_time = verify_timestamp(frontend_timestamp)

    concept_question_collection.update_one(
        {"_id": session_obj_id},
        {
            "$set": {
                "status": "passive",
                "submitted_at_frontend": frontend_time,
                "submitted_at_backend": backend_time,
            }
        }
    )

    return {"success": True}







@router.post("/questions/new")
async def generate_questions(
    concept_id: str,
    num_questions: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)
    
    concept, concept_id = verify_concept(concept_id, candidate_id)
    session_number = concept["total_sessions"] + 1   

    previous_sessions = {}
    if session_number != 1:
        previous_sessions,_ = previous_concept_session_questions(concept_id)



    try:
        questions_json = generate_concept_topic_questions(
            concept["topic"],
            num_questions,
            previous_sessions
        )
        
        questions_list = questions_json["questions"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error: {str(e)}")
    
    question_bank = []
    time = num_questions * 10

    for i, question in enumerate(questions_list, start=1):
        question_bank.append({
            "question_number": i,
            "question": question,
            "answer": "",
            "feedback": "",
            "score": ""
        })


    timestamp = generate_timestamp()
    session_doc = {
        "session_number": session_number,
        "concept_id": concept_id,
        "time": time,
        "question_bank": question_bank,
        "overall_feedback": "",
        "overall_score": "",
        "status": "active",
        "timestamp": timestamp
    }

    inserted = concept_question_collection.insert_one(session_doc)
    question_session_id = inserted.inserted_id

    concept_collection.update_one(
        {"_id": concept_id},
        {
            "$inc": {
                "total_sessions": 1
            }
        }
    )

    formatted_questions = {
        i + 1: q for i, q in enumerate(questions_list)
    }

    asyncio.create_task(
        auto_submit(
            str(concept_id),
            question_session_id=str(question_session_id),
            token=token,
            start_time = timestamp,
            duration = time,
            fun = submit_session
        )
    )




    return {
        "concept_id": str(concept_id),
        "question_session_id": str(question_session_id),
        "time": time,
        "questions": formatted_questions
    }


@router.post("/questions/save")
def save_answer(
    concept_id: str,
    question_session_id: str,
    question_number: int,
    answer: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        concept_obj_id
    )
    verify_session_status(session_doc)
    verify_session_time(session_doc, session_obj_id)
    verify_question_number(session_doc, question_number)


    concept_question_collection.update_one(
        {
            "_id": session_obj_id,
            "question_bank.question_number": question_number
        },
        {
            "$set": {
                "question_bank.$.answer": answer
            }
        }
    )

    return {"success": True}






@router.put("/questions/reattempt")
def reattempt_session(
    concept_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)
    old_session_doc, old_session_obj_id = verify_question_session(
        question_session_id,
        concept_obj_id
    )


    new_question_bank = []

    for q in old_session_doc["question_bank"]:
        new_question_bank.append({
            "question_number": q["question_number"],
            "question": q["question"],
            "answer": "",
            "feedback": "",
            "score": ""
        })

    timestamp = generate_timestamp()
    new_doc = {
        "session_number": old_session_doc["session_number"],
        "concept_id": concept_obj_id,
        "time": old_session_doc["time"],
        "question_bank": new_question_bank,
        "overall_feedback": "",
        "overall_score": "",
        "status": "active",
        "timestamp": timestamp
    }

    inserted = concept_question_collection.insert_one(new_doc)
    new_session_id = inserted.inserted_id

    asyncio.create_task(
        auto_submit(
            concept_id,
            question_session_id=question_session_id,
            token=token,
            start_time = timestamp,
            duration = old_session_doc["time"],
            fun = submit_session
        )
    )

    return {
        "new_question_session_id": str(new_session_id)
    }


@router.patch("/questions/fake/submit")
def fake_submit_session(
    concept_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        concept_obj_id
    )
    verify_session_status(session_doc)


    timestamp = session_doc.get("timestamp")
    time = session_doc.get("time")


    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    auto_submit_time = timestamp + timedelta(
        minutes=time + 1
    )

    concept_question_collection.update_one(
        {"_id": session_obj_id},
        {
            "$set": {
                "status": "passive",
                "submitted_at_frontend": auto_submit_time,
                "submitted_at_backend": auto_submit_time
            }
        }
    )

    return {
        "success": True
    }



@router.get("/questions/feedback")
def generate_feedback(
    concept_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        concept_obj_id
    )
    verify_session_status2(session_doc)

    try:
        feedback_result = evaluate_concept_topic_answers(
            concept_doc["topic"],
            session_doc["question_bank"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI evaluation failed: {str(e)}"
        )

    feedback_per_question = feedback_result["feedback_per_question"]
    overall_feedback = feedback_result["overall_feedback"]
    overall_score = feedback_result["overall_score"]

    updated_question_bank = session_doc["question_bank"]

    feedback_map = {
        item["question_number"]: item
        for item in feedback_per_question
    }

    for q in updated_question_bank:
        qn = q["question_number"]
        if qn in feedback_map:
            q["feedback"] = feedback_map[qn]["feedback"]
            q["score"] = feedback_map[qn]["score"]

    concept_question_collection.update_one(
        {"_id": session_obj_id},
        {
            "$set": {
                "question_bank": updated_question_bank,
                "overall_feedback": overall_feedback,
                "overall_score": overall_score
            }
        }
    )


    return {
        "question_session_id": str(session_obj_id),
        "overall_feedback": overall_feedback,
        "overall_score": overall_score,
        "question_bank": updated_question_bank
    }



@router.get("/questions/sessions")
def get_all_sessions(
    concept_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)

    sessions = concept_question_collection.find(
        {"concept_id": concept_obj_id},
        {
            "_id": 1,
            "session_number": 1,
            "timestamp": 1
        }
    ).sort("timestamp", 1)

    session_list = [
        {
            "question_session_id": str(doc["_id"]),
            "session_number": doc.get("session_number"),
            "timestamp": doc.get("timestamp")
        }
        for doc in sessions
    ]

    return {
        "concept_id": str(concept_obj_id),
        "sessions": session_list
    }



@router.get("/questions/data")
def get_session_data(
    concept_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        concept_obj_id
    )

    session_doc["_id"] = str(session_doc["_id"])
    session_doc["concept_id"] = str(session_doc["concept_id"])

    return {
        "concept_id": str(concept_obj_id),
        "session": session_doc
    }




@router.delete("/delete")
def delete_concept(
    concept_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)

    concept_question_collection.delete_many({
        "concept_id": concept_obj_id
    })

    concept_collection.delete_one({
        "_id": concept_obj_id
    })

    return {"success": True}


@router.delete("/questions/delete")
def delete_session(
    concept_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        concept_obj_id
    )

    session_number = session_doc["session_number"]

    count_same_number = concept_question_collection.count_documents({
        "concept_id": concept_obj_id,
        "session_number": session_number
    })

    if count_same_number == 1:
        raise HTTPException(
            status_code=400,
            detail="Can't delete complete session entirely, either reattempt or leave."
        )

    concept_question_collection.delete_one({
        "_id": session_obj_id
    })

    return {"success": True}




@router.put("/questions/delete-reattempt")
def delete_and_reattempt(
    concept_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        concept_obj_id
    )


    new_question_bank = []

    for q in session_doc["question_bank"]:
        new_question_bank.append({
            "question_number": q["question_number"],
            "question": q["question"],
            "answer": "",
            "feedback": "",
            "score": ""
        })

    timestamp = generate_timestamp()

    concept_question_collection.update_one(
        {"_id": session_obj_id},
        {
            "$set": {
                "question_bank": new_question_bank,
                "overall_feedback": "",
                "overall_score": "",
                "status": "active",
                "timestamp": timestamp
            },
            "$unset": {
                "submitted_at_frontend": "",
                "submitted_at_backend": ""
            }
        }
    )

    asyncio.create_task(
        auto_submit(
            concept_id,
            question_session_id=question_session_id,
            token=token,
            start_time = timestamp,
            duration = session_doc["time"],
            fun = submit_session
        )
    )

    return {"success": True}






@router.get("/questions/combined-feedback")
def combined_feedback_last_x_sessions(
    concept_id: str,
    x: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    if x <= 1:
        raise HTTPException(status_code=400, detail="Invalid value of x")

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)

    session_dict, sessions_used = previous_concept_session_questions(
    concept_obj_id,x=x)
    
    feedback = generate_concept_combined_diff_session_feedback(concept_doc["topic"], session_dict)

    concept_collection.update_one(
        {"_id": concept_obj_id},
        {
            "$push": {
                "combined_feedback": {
                    "sessions_used": sessions_used,
                    "feedback": feedback,
                    "type": "different",
                    "timestamp": generate_timestamp()
                }
            }
        }
    )

    return {
        "sessions_used": sessions_used,
        "feedback": feedback
    }



@router.get("/questions/session-progress-feedback")
def combined_feedback_same_session(
    concept_id: str,
    question_session_id: str,
    x: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    if x <= 1:
        raise HTTPException(status_code=400, detail="Invalid value of x")

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    concept_doc, concept_obj_id = verify_concept(concept_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        concept_obj_id
    )

    session_number = session_doc["session_number"]

    session_dict, sessions_used = previous_concept_session_questions(
    concept_obj_id,
    x=x,
    session_number=session_number)

    feedback = generate_concept_combined_same_session_feedback(concept_doc["topic"], session_dict)


    concept_collection.update_one(
        {"_id": concept_obj_id},
        {
            "$push": {
                "combined_feedback": {
                    "sessions_used": sessions_used,
                    "feedback": feedback,
                    "type":"same",
                    "timestamp": generate_timestamp()
                }
            }
        }
    )

    return {
        "sessions_used": sessions_used,
        "feedback": feedback
    }














