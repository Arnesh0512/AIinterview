from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from tempfile import NamedTemporaryFile
import shutil
import os
from database import resume_collection, resume_question_collection, resume_fs, candidate_collection
from prompt.resume import process_resume, generate_resume_question, evaluate_resume_answers, generate_resume_combined_diff_session_feedback, generate_resume_combined_same_session_feedback
from verify.token import verify_access_token
from verify.candidate import verify_candidate_payload
from verify.resume import verify_resume, verify_question_session, verify_session_status, verify_session_time, verify_question_number, verify_session_status2, verify_file_id
from fastapi.responses import StreamingResponse
from datetime import datetime, timedelta, timezone
from utils.resume import previous_resume_session_questions
from utils.time import generate_timestamp

router = APIRouter(
    prefix="/resume",
    tags=["Resume"]
)

security = HTTPBearer()


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    ocr_mode: str = "N",
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF allowed")

    original_filename = file.filename

    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        summary = process_resume(temp_path, ocr_mode)
    
        with open(temp_path, "rb") as f:
            file_id = resume_fs.put(
                f,
                filename=original_filename,
                content_type="application/pdf"
            )

        resume_doc = {
            "candidate_id": candidate_id,
            "resume_number": candidate["total_resumes"]+1,
            "summary": summary,
            "file_id": file_id,
            "filename": original_filename,
            "created_on": generate_timestamp(),
            "total_sessions":0
        }

        result = resume_collection.insert_one(resume_doc)

        candidate_collection.update_one(
            {"_id": candidate_id},
            {
                "$inc": {
                    "total_resumes": 1
                }
            }
        )

    finally:
        os.remove(temp_path)

    return {
        "success": True
    }



@router.get("/all")
def get_all_resume_ids(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resumes = resume_collection.find(
        {"candidate_id": candidate_id},
        {"_id": 1, "resume_number":1, "file_id": 1, "filename": 1, "created_on":1}
    ).sort("created_on", -1)

    resume_list = [
        {
            "resume_id": str(doc["_id"]),
            "resume_number": doc.get("resume_number"),
            "file_id": str(doc.get("file_id")) if doc.get("file_id") else None,
            "filename": doc.get("filename"),
            "created_on": doc.get("created_on")
        }
        for doc in resumes
    ]

    return {
        "success": True,
        "resumes": resume_list
    }




@router.get("/file")
def get_resume_file(
    file_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    file_obj_id = verify_file_id(file_id)

    grid_out = resume_fs.get(file_obj_id)

    return StreamingResponse(
        grid_out,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{grid_out.filename}"'
        }
    )





@router.post("/questions/new")
def generate_questions(
    resume_id: str,
    num_questions: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)
    
    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    session_number = resume_doc["total_sessions"] + 1   

    
    previous_sessions = {}
    if session_number != 1:
        previous_sessions,_ = previous_resume_session_questions(resume_obj_id)



    try:
        questions_json = generate_resume_question(
            resume_doc["summary"],
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
        "resume_id": resume_obj_id,
        "time": time,
        "question_bank": question_bank,
        "overall_feedback": "",
        "overall_score": "",
        "status": "active",
        "timestamp": timestamp
    }

    inserted = resume_question_collection.insert_one(session_doc)
    question_session_id = inserted.inserted_id

    resume_collection.update_one(
        {"_id": resume_obj_id},
        {
            "$set": {
                f"question_session_ids.{str(question_session_id)}": timestamp
            },
            "$inc": {
                "total_sessions": 1
            }
        }
    )

    formatted_questions = {
        i + 1: q for i, q in enumerate(questions_list)
    }

    

    return {
        "resume_id": str(resume_obj_id),
        "question_session_id": str(question_session_id),
        "time": time,
        "questions": formatted_questions
    }









@router.post("/questions/save")
def save_answer(
    resume_id: str,
    question_session_id: str,
    question_number: int,
    answer: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        resume_obj_id
    )
    verify_session_status(session_doc)
    verify_session_time(session_doc, session_obj_id)
    verify_question_number(session_doc, question_number)


    resume_question_collection.update_one(
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


@router.post("/questions/submit")
def submit_session(
    resume_id: str,
    question_session_id: str,
    frontend_timestamp: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        resume_obj_id
    )

    verify_session_status(session_doc)
    verify_session_time(session_doc, session_obj_id)


    try:
        frontend_time = datetime.fromisoformat(frontend_timestamp)

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

    resume_question_collection.update_one(
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


@router.patch("/questions/autosubmit")
def auto_submit_session(
    resume_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        resume_obj_id
    )

    if session_doc.get("status") == "passive":
        return {"success": True, "message": "Already submitted"}


    timestamp = session_doc.get("timestamp")
    time = session_doc.get("time")


    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    auto_submit_time = timestamp + timedelta(
        minutes=time + 1
    )

    resume_question_collection.update_one(
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


@router.put("/questions/reattempt")
def reattempt_session(
    resume_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    old_session_doc, old_session_obj_id = verify_question_session(
        question_session_id,
        resume_obj_id
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
        "resume_id": resume_obj_id,
        "time": old_session_doc["time"],
        "question_bank": new_question_bank,
        "overall_feedback": "",
        "overall_score": "",
        "status": "active",
        "timestamp": timestamp
    }

    inserted = resume_question_collection.insert_one(new_doc)
    new_session_id = inserted.inserted_id

    resume_collection.update_one(
        {"_id": resume_obj_id},
        {
            "$set": {
                f"question_session_ids.{str(new_session_id)}": timestamp
            }
        }
    )

    return {
        "new_question_session_id": str(new_session_id)
    }


@router.get("/questions/feedback")
def generate_feedback(
    resume_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        resume_obj_id
    )
    verify_session_status2(session_doc)

    try:
        feedback_result = evaluate_resume_answers(
            resume_doc["summary"],
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

    resume_question_collection.update_one(
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
    resume_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)

    sessions = resume_question_collection.find(
        {"resume_id": resume_obj_id},
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
        "resume_id": str(resume_obj_id),
        "sessions": session_list
    }


@router.get("/questions/data")
def get_session_data(
    resume_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        resume_obj_id
    )

    session_doc["_id"] = str(session_doc["_id"])
    session_doc["resume_id"] = str(session_doc["resume_id"])

    return {
        "resume_id": str(resume_obj_id),
        "session": session_doc
    }




@router.delete("/delete")
def delete_resume(
    resume_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)

    resume_question_collection.delete_many({
        "resume_id": resume_obj_id
    })

    file_id = resume_doc.get("file_id")
    if file_id:
        resume_fs.delete(file_id)

    resume_collection.delete_one({
        "_id": resume_obj_id
    })

    return {"success": True}


@router.delete("/questions/delete")
def delete_session(
    resume_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        resume_obj_id
    )

    session_number = session_doc["session_number"]

    count_same_number = resume_question_collection.count_documents({
        "resume_id": resume_obj_id,
        "session_number": session_number
    })

    if count_same_number == 1:
        raise HTTPException(
            status_code=400,
            detail="Can't delete complete session entirely, either reattempt or leave."
        )

    resume_question_collection.delete_one({
        "_id": session_obj_id
    })

    return {"success": True}




@router.put("/questions/delete-reattempt")
def delete_and_reattempt(
    resume_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        resume_obj_id
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

    resume_question_collection.update_one(
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

    return {"success": True}






@router.get("/questions/combined-feedback")
def combined_feedback_last_x_sessions(
    resume_id: str,
    x: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    if x <= 1:
        raise HTTPException(status_code=400, detail="Invalid value of x")

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)

    session_dict, sessions_used = previous_resume_session_questions(
    resume_obj_id,x=x)
    
    feedback = generate_resume_combined_diff_session_feedback(resume_doc["summary"], session_dict)

    resume_collection.update_one(
        {"_id": resume_obj_id},
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
    resume_id: str,
    question_session_id: str,
    x: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    if x <= 1:
        raise HTTPException(status_code=400, detail="Invalid value of x")

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    resume_doc, resume_obj_id = verify_resume(resume_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        resume_obj_id
    )

    session_number = session_doc["session_number"]

    session_dict, sessions_used = previous_resume_session_questions(
    resume_obj_id,
    x=x,
    session_number=session_number)

    feedback = generate_resume_combined_same_session_feedback(resume_doc["summary"], session_dict)


    resume_collection.update_one(
        {"_id": resume_obj_id},
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






