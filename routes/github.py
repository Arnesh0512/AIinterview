from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone, timedelta
from database import github_collection, github_question_collection
from verify.token import verify_access_token
from verify.candidate import verify_candidate_payload
from utils.github import fetch_repositories
from prompt.github import process_repo, generate_github_question, evaluate_github_answers
from verify.github import verify_github_link, verify_github_link_repo, verify_github, verify_question_number, verify_question_session, verify_session_status, verify_session_status2, verify_session_time
from utils.time import generate_timestamp

router = APIRouter(
    prefix="/github",
    tags=["GitHub"]
)

security = HTTPBearer()


@router.post("/repos")
def get_repositories(
    github_link: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    verify_github_link(github_link)
    repo_list = fetch_repositories(github_link)

    return {
        "success": True,
        "github_link": github_link,
        "repositories": repo_list
    }


@router.post("/repo")
def get_repository_details(
    github_link: str,
    repo_link: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    verify_github_link_repo(github_link, repo_link)
    repo_details = process_repo(repo_link)

    github_doc = {
        "candidate_id": candidate_id,
        "github_link": github_link,
        "repo_name": repo_details["repo_name"],
        "repo_link": repo_link,
        "summary": repo_details["summary"],
        "created_on": generate_timestamp()
    }

    github_insert_result = github_collection.insert_one(github_doc)
    github_id = github_insert_result.inserted_id

    return {
        "success": True
    }


@router.get("/all")
def get_all_github_ids(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    githubs = github_collection.find(
        {"candidate_id": candidate_id},
        {"_id": 1, "repo_name": 1, "repo_link": 1, "created_on":1}
    ).sort("created_on", -1)

    github_list = [
        {
            "github_id": str(doc["_id"]),
            "repo_name": doc.get("repo_name"),
            "repo_link": doc.get("repo_link"),
            "created_on": doc.get("created_on")
        }
        for doc in githubs
    ]

    return {
        "success": True,
        "githubs": github_list
    }













@router.post("/questions/new")
def generate_github_questions(
    github_id: str,
    num_questions: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    github_doc, github_obj_id = verify_github(github_id, candidate_id)

    try:
        questions_json = generate_github_question(
            github_doc["summary"],
            num_questions
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


    nlist = github_question_collection.find(
        {"github_id": github_obj_id},
        {"session_number": 1, "_id": 0}
    )
    nlist = [doc["session_number"] for doc in nlist]
    session_number = max(list(set(nlist))) + 1 if nlist else 1

    timestamp = generate_timestamp()
    session_doc = {
        "session_number": session_number,
        "github_id": github_obj_id,
        "time": time,
        "question_bank": question_bank,
        "overall_feedback": "",
        "overall_score": "",
        "status": "active",
        "timestamp": timestamp
    }

    inserted = github_question_collection.insert_one(session_doc)
    question_session_id = inserted.inserted_id


    github_collection.update_one(
        {"_id": github_obj_id},
        {
            "$set": {
                f"question_session_ids.{str(question_session_id)}":timestamp
            }
        }
    )

    formatted_questions = {
        i + 1: q for i, q in enumerate(questions_list)
    }

    return {
        "github_id": str(github_obj_id),
        "question_session_id": str(question_session_id),
        "time": time,
        "questions": formatted_questions
    }



@router.post("/questions/save")
def save_answer(
    github_id: str,
    question_session_id: str,
    question_number: int,
    answer: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    github_doc, github_obj_id = verify_github(github_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        github_obj_id
    )
    verify_session_status(session_doc)
    verify_session_time(session_doc, session_obj_id)
    verify_question_number(session_doc, question_number)


    github_question_collection.update_one(
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
    github_id: str,
    question_session_id: str,
    frontend_timestamp: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    github_doc, github_obj_id = verify_github(github_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        github_obj_id
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

    github_question_collection.update_one(
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




@router.post("/questions/autosubmit")
def auto_submit_session(
    github_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    github_doc, github_obj_id = verify_github(github_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        github_obj_id
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

    github_question_collection.update_one(
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














@router.post("/questions/reattempt")
def reattempt_session(
    github_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    github_doc, github_obj_id = verify_github(github_id, candidate_id)
    old_session_doc, old_session_obj_id = verify_question_session(
        question_session_id,
        github_obj_id
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
        "github_id": github_obj_id,
        "time": old_session_doc["time"],
        "question_bank": new_question_bank,
        "overall_feedback": "",
        "overall_score": "",
        "status": "active",
        "timestamp": timestamp
    }

    inserted = github_question_collection.insert_one(new_doc)
    new_session_id = inserted.inserted_id

    github_collection.update_one(
        {"_id": github_obj_id},
        {
            "$set": {
                f"question_session_ids.{str(new_session_id)}": timestamp
            }
        }
    )

    return {
        "new_question_session_id": str(new_session_id)
    }



@router.post("/questions/feedback")
def generate_feedback(
    github_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    github_doc, github_obj_id = verify_github(github_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        github_obj_id
    )
    verify_session_status2(session_doc)

    try:
        feedback_result = evaluate_github_answers(
            github_doc["summary"],
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

    github_question_collection.update_one(
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
    github_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    github_doc, github_obj_id = verify_github(github_id, candidate_id)

    sessions = github_question_collection.find(
        {"github_id": github_obj_id},
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
        "github_id": str(github_obj_id),
        "sessions": session_list
    }


@router.get("/questions/history")
def get_session_history(
    github_id: str,
    question_session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)

    github_doc, github_obj_id = verify_github(github_id, candidate_id)
    session_doc, session_obj_id = verify_question_session(
        question_session_id,
        github_obj_id
    )

    session_doc["_id"] = str(session_doc["_id"])
    session_doc["github_id"] = str(session_doc["github_id"])

    return {
        "github_id": str(github_obj_id),
        "session": session_doc
    }

