from fastapi import APIRouter, Depends,HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone, timedelta
from database import leetcode, coding_collection, coding_question_collection, candidate_collection
from verify.token import verify_access_token
from verify.candidate import verify_candidate_payload
from constants.company import CompanyEnum
from constants.tag import TagEnum
from constants.difficulty import DifficultyEnum
from constants.language import LanguageEnum
from typing import Optional, List
from verify.coding import verify_coding, verify_quantity, verify_question_session, verify_session_status, verify_session_status2, verify_session_time, verify_question_id, verify_timestamp
from prompt.coding import evaluate_coding_answers, generate_coding_combined_diff_session_feedback, generate_coding_combined_same_session_feedback
from utils.coding import get_used_coding_question_ids ,previous_coding_session_questions, auto_submit
from utils.time import generate_timestamp
import asyncio

router = APIRouter(prefix="/leetcode", tags=["Coding"])
security = HTTPBearer()


@router.post("/start-coding")
def start_coding(
    company: Optional[List[CompanyEnum]] = None,
    tag: Optional[List[TagEnum]] = None,
    difficulty: Optional[List[DifficultyEnum]] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    query = {}

    if company:
        query["companies"] = {"$in": [c.value for c in company]}

    if tag:
        query["tags"] = {"$in": [t.value for t in tag]}


    if difficulty:
        query["difficulty"] = {"$in": [d.value for d in difficulty]}

    available_ques = leetcode.count_documents(query)

    if available_ques == 0:
        return {
            "success": False,
            "message": "No questions found for given filters."
        }

    coding_doc = {
    "candidate_id": candidate_id,
    "coding_number": candidate["total_codings"]+1,
    "company": [c.value for c in company] if company else [],
    "difficulty": [d.value for d in difficulty] if difficulty else [],
    "tag": [t.value for t in tag] if tag else [],
    "available_ques": available_ques,
    "created_on": generate_timestamp(),
    "total_sessions":0
    }
    
    result = coding_collection.insert_one(coding_doc)

    candidate_collection.update_one(
        {"_id": candidate_id},
        {
            "$inc": {
                "total_codings": 1
            }
        }
    )

    return {
        "success": True
    }




@router.get("/all")
def get_all_coding_ids(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    codings = coding_collection.find(
        {"candidate_id": candidate_id},
        {"candidate_id": 0}
    ).sort("created_on", -1)

    coding_list = []

    for doc in codings:
        coding_list.append({
            "coding_id": str(doc["_id"]),
            "coding_number": doc.get("coding_number"),
            "company": doc.get("company", []),
            "difficulty": doc.get("difficulty", []),
            "tag": doc.get("tag", []),
            "available_ques": doc.get("available_ques"),
            "created_on": doc.get("created_on")
        })

    return {
        "success": True,
        "codings": coding_list
    }




@router.post("/questions/submit")
def submit_session(
    coding_id: str,
    question_session_id: str,
    frontend_timestamp: datetime,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        coding_obj_id
    )

    verify_session_status(session_doc)
    verify_session_time(session_doc, session_obj_id)
    frontend_time , backend_time = verify_timestamp(frontend_timestamp)



    coding_question_collection.update_one(
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
    coding_id: str,
    num_questions: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)
    coding, coding_id = verify_coding(coding_id, candidate_id)

    verify_quantity(num_questions, coding)


    query = {}

    if coding.get("company"):
        query["companies"] = {"$in": coding["company"]}

    if coding.get("tag"):
        query["tags"] = {"$in": coding["tag"]}

    if coding.get("difficulty"):
        query["difficulty"] = {"$in": coding["difficulty"]}


    session_number = coding["total_sessions"] + 1       

    if session_number > 1:
        query["question_id"] = {"$nin": get_used_coding_question_ids(coding_id)}


    pipeline = [
        {"$match": query},
        {"$sample": {"size": num_questions}}
    ]

    questions_cursor = leetcode.aggregate(pipeline)
    questions_list = list(questions_cursor)
    available_count = len(questions_list)


    if available_count == 0:
        return {
           "success":False,
           "message":"No questions available"
        }

    question_bank = []
    time = available_count * 60

    for q in questions_list:
        question_bank.append({
            "question_id": q["question_id"],
            "language": "",
            "answer": "",
            "feedback": "",
            "score": ""
        })


    timestamp = generate_timestamp()
    session_doc = {
        "session_number": session_number,
        "coding_id": coding_id,
        "time": time,
        "question_bank": question_bank,
        "overall_feedback": "",
        "overall_score": "",
        "status": "active",
        "timestamp": timestamp
    }

    inserted = coding_question_collection.insert_one(session_doc)
    question_session_id = inserted.inserted_id


    coding_collection.update_one(
        {"_id": coding_id},
        {
            "$inc": {
                "total_sessions": 1
            }
        }
    )

    formatted_questions = [
        {
            "question_id": q["question_id"],
            "task_name": q["task_name"],
            "problem_description": q["problem_description"]
        }
        for q in questions_list
    ]

    asyncio.create_task(
        auto_submit(
            str(coding_id),
            question_session_id=str(question_session_id),
            token=token,
            start_time = timestamp,
            duration = time,
            fun = submit_session
        )
    )

    return {
        "success":True,
        "coding_id": str(coding_id),
        "question_session_id": str(question_session_id),
        "time": time,
        "questions": formatted_questions
    }




@router.post("/questions/save")
def save_answer(
    coding_id: str,
    question_session_id: str,
    question_id: int,
    language: LanguageEnum ,
    answer: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)



    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        coding_obj_id
    )


    verify_session_status(session_doc)
    verify_session_time(session_doc, session_obj_id)
    verify_question_id(session_doc, question_id)


    coding_question_collection.update_one(
        {
            "_id": session_obj_id,
            "question_bank.question_id": question_id
        },
        {
            "$set": {
                "question_bank.$.language": language,
                "question_bank.$.answer": answer
            }
        }
    )

    return {"success": True}
















@router.put("/questions/reattempt")
def reattempt_session(
    coding_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)
    old_session_doc, old_session_obj_id = verify_question_session(
        question_session_id,
        coding_obj_id
    )


    new_question_bank = []

    for q in old_session_doc["question_bank"]:
        new_question_bank.append({
            "question_id": q["question_id"],
            "language": "",
            "answer": "",
            "feedback": "",
            "score": ""
        })

    timestamp = generate_timestamp()
    new_doc = {
        "session_number": old_session_doc["session_number"],
        "coding_id": coding_obj_id,
        "time": old_session_doc["time"],
        "question_bank": new_question_bank,
        "overall_feedback": "",
        "overall_score": "",
        "status": "active",
        "timestamp": timestamp
    }

    inserted = coding_question_collection.insert_one(new_doc)
    new_session_id = inserted.inserted_id

    asyncio.create_task(
        auto_submit(
            coding_id,
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
    coding_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        coding_obj_id
    )
    verify_session_status(session_doc)


    timestamp = session_doc.get("timestamp")
    time = session_doc.get("time")


    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    auto_submit_time = timestamp + timedelta(
        minutes=time + 1
    )

    coding_question_collection.update_one(
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
    coding_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        coding_obj_id
    )
    verify_session_status2(session_doc)

    

    question_ids = [q["question_id"] for q in session_doc.get("question_bank")]
    question_docs = list(
        leetcode.find(
            {"question_id": {"$in": question_ids}},
            {"question_id": 1, "problem_description": 1, "_id": 0}
        )
    )
    question_map = {
        doc["question_id"]: doc["problem_description"]
        for doc in question_docs
    }

    enriched_questions = []
    for q in session_doc.get("question_bank"):
        qid = q["question_id"]

        enriched_questions.append({
            "question_id": qid,
            "problem_description": question_map[qid],
            "language": q.get("language"),
            "answer": q.get("answer", "")
        })

    
    try:
        feedback_result = evaluate_coding_answers(enriched_questions)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI evaluation failed: {str(e)}"
        )

    feedback_per_question = feedback_result["feedback_per_question"]
    overall_feedback = feedback_result["overall_feedback"]
    overall_score = feedback_result["overall_score"]

    feedback_map = {
        item["question_id"]: item
        for item in feedback_per_question
    }

    updated_question_bank = session_doc.get("question_bank")

    for q in updated_question_bank:
        qid = q["question_id"]
        if qid in feedback_map:
            q["feedback"] = feedback_map[qid]["feedback"]
            q["score"] = feedback_map[qid]["score"]

    coding_question_collection.update_one(
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
    coding_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)

    sessions = coding_question_collection.find(
        {"coding_id": coding_obj_id},
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
        "coding_id": str(coding_obj_id),
        "sessions": session_list
    }



@router.get("/questions/data")
def get_session_data(
    coding_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        coding_obj_id
    )

    session_doc["_id"] = str(session_doc["_id"])
    session_doc["coding_id"] = str(session_doc["coding_id"])

    return {
        "coding_id": str(coding_obj_id),
        "session": session_doc
    }





@router.delete("/delete")
def delete_coding(
    coding_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)

    coding_question_collection.delete_many({
        "coding_id": coding_obj_id
    })

    coding_collection.delete_one({
        "_id": coding_obj_id
    })

    return {"success": True}


@router.delete("/questions/delete")
def delete_session(
    coding_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        coding_obj_id
    )

    session_number = session_doc["session_number"]

    count_same_number = coding_question_collection.count_documents({
        "coding_id": coding_obj_id,
        "session_number": session_number
    })

    if count_same_number == 1:
        raise HTTPException(
            status_code=400,
            detail="Can't delete complete session entirely, either reattempt or leave."
        )

    coding_question_collection.delete_one({
        "_id": session_obj_id
    })

    return {"success": True}




@router.put("/questions/delete-reattempt")
def delete_and_reattempt(
    coding_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        coding_obj_id
    )


    new_question_bank = []

    for q in session_doc["question_bank"]:
        new_question_bank.append({
            "question_id": q["question_id"],
            "language": "",
            "answer": "",
            "feedback": "",
            "score": ""
        })

    timestamp = generate_timestamp()

    coding_question_collection.update_one(
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
            coding_id,
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
    coding_id: str,
    x: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    if x <= 1:
        raise HTTPException(status_code=400, detail="Invalid value of x")

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)

    session_dict, sessions_used = previous_coding_session_questions(
    coding_obj_id,x=x)
    
    feedback = generate_coding_combined_diff_session_feedback(session_dict)

    coding_collection.update_one(
        {"_id": coding_obj_id},
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
    coding_id: str,
    question_session_id: str,
    x: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    if x <= 1:
        raise HTTPException(status_code=400, detail="Invalid value of x")

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    coding_doc, coding_obj_id = verify_coding(coding_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        coding_obj_id
    )

    session_number = session_doc["session_number"]

    session_dict, sessions_used = previous_coding_session_questions(
    coding_obj_id,
    x=x,
    session_number=session_number)

    feedback = generate_coding_combined_same_session_feedback(session_dict)


    coding_collection.update_one(
        {"_id": coding_obj_id},
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














