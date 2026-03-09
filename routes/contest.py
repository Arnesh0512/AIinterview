from verify.contest import verify_contest_id, verify_candidate_eligibility, verify_contest_registry
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from tempfile import NamedTemporaryFile
import shutil
import os
from verify.token import verify_access_token
from verify.candidate import verify_candidate_payload
from utils.time import generate_timestamp
from verify.contest import verify_resume_time_open, verify_timestamp, verify_coding_time_open, verify_coding_submit
from utils.resume import extract_text_with_ocr, extract_text_without_ocr
from prompt.contest import evaluate_resume_score, generate_summary
from database import contest_collection, contest_candidate_collection, contest_resume_fs, contest_audio_fs,contest_leaderboard, candidate_collection, leetcode
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from verify.contest import verify_resume_result_time,verify_coding_result_time, verify_candidate_passed_resume, verify_coding_question, verify_coding_time, verify_candidate_passed_coding
from utils.contest import auto_submit, generate_coding_scores, generate_concept_scores, generate_hr_scores
import asyncio
from verify.contest import verify_concept_time_open, verify_concept_question, verify_concept_time, verify_concept_result_time, verify_concept_submit, verify_candidate_passed_concept
from verify.contest import verify_hr_time_open, verify_hr_question, verify_hr_time, verify_hr_submit, verify_hr_result_time
import tempfile
from database import contest_audio_fs
from model import call_audio_model_1



security = HTTPBearer()

router = APIRouter(
    prefix="/contest",
    tags=["contest"]
)


@router.get("/available")
def fetch_available_contests(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)

    candidate_roles = [r.value for r in candidate["roles"]]
    candidate_skills = [s.value for s in candidate["skills"]]

    contests = contest_collection.find(
        {
            "role": {"$in": candidate_roles},
            "skills": {"$in": candidate_skills}
        },
        {
            "_id": 1,
            "company": 1,
            "role": 1,
            "skills": 1,
            "contest_start": 1,
            "contest_end": 1,
            "last_date_to_register": 1,
            "candidate_capacity": 1,
            "candidate_count": 1,
            "created_on": 1
        }
    ).sort("created_on", -1)

    result = []

    for c in contests:
        result.append({
            "contest_id": str(c["_id"]),
            "company": c["company"],
            "role": c["role"],
            "skills": c["skills"],
            "contest_start": c["contest_start"],
            "contest_end": c["contest_end"],
            "last_date_to_register": c["last_date_to_register"],
            "candidate_capacity": c["candidate_capacity"],
            "candidate_count": c["candidate_count"],
            "created_on": c["created_on"]
        })

    return {
        "success": True,
        "data": result
    }


@router.get("/details")
def fetch_contest_details(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)


    contest.pop("admin_created_id", None)
    contest.pop("registered_candidates", None)
    contest["resume_round"].pop("questions", None)
    contest["coding_round"].pop("questions", None)
    contest["concept_round"].pop("questions", None)
    contest["hr_round"].pop("questions", None)
    contest["_id"] = str(contest["_id"])

    return {
        "success": True,
        "data": contest
    }






@router.post("/register")
def register_for_contest(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)

    timestamp = generate_timestamp()

    verify_candidate_eligibility(timestamp, candidate, contest)
    verify_contest_registry(candidate, contest, "N")
    
    

    update_result = contest_collection.update_one(
        {
            "_id": contest_obj_id,
            "candidate_count": {"$lt": contest["candidate_capacity"]},
            "registered_candidates": {"$ne": candidate_id}
        },
        {
            "$addToSet": {"registered_candidates": candidate_id},
            "$inc": {"candidate_count": 1}
        }
    )

    if update_result.modified_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Contest full or already registered"
        )

    contest_candidate_collection.insert_one({
        "contest_id": contest_obj_id,
        "candidate_id": candidate_id,
        "created_on": timestamp
    })

    return {
        "success": True,
        "message": "Registered successfully"
    }






































@router.post("/resume/submit")
async def submit_resume_for_contest(
    contest_id: str,
    frontend_timestamp : datetime,
    file: UploadFile = File(...),
    ocr_mode: str = "N",
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    backend_timestamp = generate_timestamp()
    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)


    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    timestamp = verify_timestamp(frontend_timestamp, backend_timestamp)
    verify_resume_time_open(timestamp, contest)

    if contest_candidate.get("resume"):
        raise HTTPException(
            status_code=400,
            detail="Resume already submitted"
        )

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF allowed")


    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name


    try:
        if ocr_mode.upper() == "Y":
            resume_text = extract_text_with_ocr(temp_path)
        else:
            resume_text = extract_text_without_ocr(temp_path)

        if not resume_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No text extracted from PDF"
            )


        questions = contest["resume_round"]["questions"]

        response = evaluate_resume_score(
            resume_text, questions, 
            contest["company"], contest["role"], contest["skills"])
        
        question_bank = response["results"]
        overall_feedback = response["overall_feedback"]
        
        summary = generate_summary(resume_text)

        with open(temp_path, "rb") as f:
            file_id = contest_resume_fs.put(
                f,
                filename=file.filename,
                content_type="application/pdf"
            )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="AI evaluation failed"
        )

    finally:
        os.remove(temp_path)


    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id
        },
        {
            "$set": {
                "resume": {
                    "file_id": file_id,
                    "summary": summary,
                    "question_bank":question_bank,
                    "overall_feedback":overall_feedback,
                    "submitted_at": timestamp
                }
            }
        }
    )


    return {
        "success": True
    }







@router.get("/leaderboard/resume")
def get_resume_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, real_candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")


    timestamp = generate_timestamp()
    verify_resume_result_time(timestamp, contest)


    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {"resume_round": 1, "_id": 0, "selected_resume_candidates":1}
    )

    if not leaderboard_doc:
        raise HTTPException(status_code=404, detail="Leaderboard not generated")

    leaderboard = leaderboard_doc["resume_round"]
    candidate_ids = [entry["candidate_id"] for entry in leaderboard]



    candidates = list(
        candidate_collection.find(
            {"_id": {"$in": candidate_ids}},
            {"_id": 1, "full_name": 1}
        )
    )
    name_map = {
        c["_id"]: c["full_name"]
        for c in candidates
    }

    result = []
    for entry in leaderboard:
        result.append({
            "candidate_id": str(real_candidate_id) if real_candidate_id == entry["candidate_id"] else None,
            "name": name_map.get(entry["candidate_id"], "Unknown"),
            "rank": entry["rank"],
            "percentile": entry["percentile"],
            "score": entry["final_normalized_score"],
            "latest_submission": entry["latest_submission"]
        })

    if real_candidate_id in leaderboard_doc["selected_resume_candidates"]:
        selection = True
    else:
        selection = False




    return {
        "success": True,
        "data": result,
        "selection": selection
    }



















@router.post("/coding/submit")
def submit_coding(
    contest_id: str,
    frontend_timestamp : datetime,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    
    backend_timestamp = generate_timestamp()
    timestamp = verify_timestamp(frontend_timestamp, backend_timestamp)

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    verify_candidate_passed_resume(candidate_id, contest_id)
    verify_coding_time(timestamp, contest, contest_candidate)
    verify_coding_submit(contest_candidate)


    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id
        },
        {
            "$set": {
                "coding.submitted_at": timestamp
            }
        }
    )

    generate_coding_scores(contest_obj_id, candidate_id, contest_candidate)

    return {
        "success": True,
        "message": "Coding submitted successfully"
    }



@router.get("/coding/questions")
async def get_coding_questions(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    verify_candidate_passed_resume(candidate_id, contest_id)
    verify_coding_time_open(generate_timestamp(), contest)

    coding_ids = contest["coding_round"]["questions"]

    questions = list(
        leetcode.find(
            {"_id": {"$in": coding_ids}},
            {
                "_id": 1,
                "task_name": 1,
                "problem_description": 1
            }
        )
    )

    result = []

    for q in questions:
        result.append({
            "question_id": str(q["_id"]),
            "task_name": q["task_name"],
            "problem_description": q["problem_description"]
        })


    schedule_autosubmit = False



    if contest_candidate.get("coding", {}) and contest_candidate.get("coding", {}).get("start_time"):
        start_time = contest_candidate["coding"]["start_time"]

    else:
        schedule_autosubmit = True
        start_time = generate_timestamp()

        question_bank = [
            {
                "question_id": qid,
                "language": None,
                "answer": None,
                "timestamp": None,
                "score": None
            }
            for qid in coding_ids
        ]



        contest_candidate_collection.update_one(
            {
                "contest_id": contest_obj_id,
                "candidate_id": candidate_id
            },
            {
                "$set": {
                    "coding.start_time": start_time,
                    "coding.question_bank":question_bank
                }
            }
        )



    if schedule_autosubmit:
        asyncio.create_task(
            auto_submit(
                contest_id,
                token,
                start_time,
                contest["coding_round"]["end"],
                contest["coding_round"]["duration"],
                submit_coding
            )
        )

    
    return {
        "success": True,
        "questions": result,
        "duration": contest["coding_round"]["duration"],
        "start_time": start_time
    }






@router.post("/coding/answer")
def submit_coding_answer(
    contest_id: str,
    question_id: str,
    answer: str,
    language: str,
    frontend_timestamp : datetime,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    
    backend_timestamp = generate_timestamp()
    timestamp = verify_timestamp(frontend_timestamp, backend_timestamp)
    

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    verify_candidate_passed_resume(candidate_id, contest_id)
    question_obj_id = verify_coding_question(contest, question_id)
    verify_coding_time(timestamp, contest, contest_candidate)
    verify_coding_submit(contest_candidate)
        


    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id,
            "coding.question_bank.question_id": question_obj_id
        },
        {
            "$set": {
                "coding.question_bank.$.language": language,
                "coding.question_bank.$.answer": answer,
                "coding.question_bank.$.timestamp": timestamp,
                "coding.question_bank.$.score": None
            }
        }
    )

    return {
        "success": True,
        "message": "Answer saved"
    }










@router.get("/leaderboard/coding")
def get_coding_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, real_candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")


    timestamp = generate_timestamp()
    verify_coding_result_time(timestamp, contest)


    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {"coding_round": 1, "_id": 0, "selected_coding_candidates":1}
    )

    if not leaderboard_doc:
        raise HTTPException(status_code=404, detail="Leaderboard not generated")

    leaderboard = leaderboard_doc["coding_round"]
    candidate_ids = [entry["candidate_id"] for entry in leaderboard]



    candidates = list(
        candidate_collection.find(
            {"_id": {"$in": candidate_ids}},
            {"_id": 1, "full_name": 1}
        )
    )
    name_map = {
        c["_id"]: c["full_name"]
        for c in candidates
    }

    result = []
    for entry in leaderboard:
        result.append({
            "candidate_id": str(real_candidate_id) if real_candidate_id == entry["candidate_id"] else None,
            "name": name_map.get(entry["candidate_id"], "Unknown"),
            "rank": entry["rank"],
            "percentile": entry["percentile"],
            "score": entry["final_normalized_score"],
            "latest_submission": entry["latest_submission"]
        })

    if real_candidate_id in leaderboard_doc["selected_coding_candidates"]:
        selection = True
    else:
        selection = False




    return {
        "success": True,
        "data": result,
        "selection": selection
    }








































@router.post("/concept/submit")
def submit_concept(
    contest_id: str,
    frontend_timestamp : datetime,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    
    backend_timestamp = generate_timestamp()
    timestamp = verify_timestamp(frontend_timestamp, backend_timestamp)

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    verify_candidate_passed_coding(candidate_id, contest_id)
    verify_concept_time(timestamp, contest, contest_candidate)
    verify_concept_submit(contest_candidate)


    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id
        },
        {
            "$set": {
                "concept.submitted_at": timestamp
            }
        }
    )

    generate_concept_scores(contest_obj_id, candidate_id, contest_candidate)

    return {
        "success": True,
        "message": "concept submitted successfully"
    }











@router.get("/concept/questions")
async def get_concept_questions(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    verify_candidate_passed_coding(candidate_id, contest_id)
    verify_concept_time_open(generate_timestamp(), contest)

    concept_questions = contest["concept_round"]["questions"]

    schedule_autosubmit = False


    if contest_candidate.get("concept", {}) and contest_candidate.get("concept", {}).get("start_time"):
        start_time = contest_candidate["concept"]["start_time"]

    else:
        schedule_autosubmit = True
        start_time = generate_timestamp()

        question_bank = [
            {
                "question_id": qid,
                "answer": None,
                "timestamp": None,
                "score": None
            }
            for qid in concept_questions
        ]



        contest_candidate_collection.update_one(
            {
                "contest_id": contest_obj_id,
                "candidate_id": candidate_id
            },
            {
                "$set": {
                    "concept.start_time": start_time,
                    "concept.question_bank":question_bank
                }
            }
        )



    if schedule_autosubmit:
        asyncio.create_task(
            auto_submit(
                contest_id,
                token,
                start_time,
                contest["concept_round"]["end"],
                contest["concept_round"]["duration"],
                submit_concept
            )
        )

    
    return {
        "success": True,
        "questions": concept_questions,
        "duration": contest["concept_round"]["duration"],
        "start_time": start_time
    }






@router.post("/concept/answer")
def submit_concept_answer(
    contest_id: str,
    question_id: str,
    answer: str,
    frontend_timestamp : datetime,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    
    backend_timestamp = generate_timestamp()
    timestamp = verify_timestamp(frontend_timestamp, backend_timestamp)
    

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    verify_candidate_passed_coding(candidate_id, contest_id)
    verify_concept_question(contest, question_id)
    verify_concept_time(timestamp, contest, contest_candidate)
    verify_concept_submit(contest_candidate)
        


    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id,
            "concept.question_bank.question_id": question_id
        },
        {
            "$set": {
                "concept.question_bank.$.answer": answer,
                "concept.question_bank.$.timestamp": timestamp,
                "concept.question_bank.$.score": None
            }
        }
    )

    return {
        "success": True,
        "message": "Answer saved"
    }







@router.get("/leaderboard/concept")
def get_concept_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, real_candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")


    timestamp = generate_timestamp()
    verify_concept_result_time(timestamp, contest)


    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {"concept_round": 1, "_id": 0, "selected_concept_candidates":1}
    )

    if not leaderboard_doc:
        raise HTTPException(status_code=404, detail="Leaderboard not generated")

    leaderboard = leaderboard_doc["concept_round"]
    candidate_ids = [entry["candidate_id"] for entry in leaderboard]



    candidates = list(
        candidate_collection.find(
            {"_id": {"$in": candidate_ids}},
            {"_id": 1, "full_name": 1}
        )
    )
    name_map = {
        c["_id"]: c["full_name"]
        for c in candidates
    }

    result = []
    for entry in leaderboard:
        result.append({
            "candidate_id": str(real_candidate_id) if real_candidate_id == entry["candidate_id"] else None,
            "name": name_map.get(entry["candidate_id"], "Unknown"),
            "rank": entry["rank"],
            "percentile": entry["percentile"],
            "score": entry["final_normalized_score"],
            "latest_submission": entry["latest_submission"]
        })

    if real_candidate_id in leaderboard_doc["selected_concept_candidates"]:
        selection = True
    else:
        selection = False




    return {
        "success": True,
        "data": result,
        "selection": selection
    }


























@router.post("/hr/submit")
def submit_hr(
    contest_id: str,
    frontend_timestamp : datetime,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    
    backend_timestamp = generate_timestamp()
    timestamp = verify_timestamp(frontend_timestamp, backend_timestamp)

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    verify_candidate_passed_concept(candidate_id, contest_id)
    verify_hr_time(timestamp, contest, contest_candidate)
    verify_hr_submit(contest_candidate)


    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id
        },
        {
            "$set": {
                "hr.submitted_at": timestamp
            }
        }
    )

    generate_hr_scores(contest_obj_id, candidate_id, contest_candidate)

    return {
        "success": True,
        "message": "hr submitted successfully"
    }











@router.get("/hr/questions")
async def get_hr_questions(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    verify_candidate_passed_concept(candidate_id, contest_id)
    verify_hr_time_open(generate_timestamp(), contest)

    hr_questions = contest["hr_round"]["questions"]

    schedule_autosubmit = False


    if contest_candidate.get("hr", {}) and contest_candidate.get("hr", {}).get("start_time"):
        start_time = contest_candidate["hr"]["start_time"]

    else:
        schedule_autosubmit = True
        start_time = generate_timestamp()

        question_bank = [
            {
                "question_id": qid,
                "audio_id": None,
                "transcript": None,
                "segmented_data": None,
                "timestamp": None,
                "score": None
            }
            for qid in hr_questions
        ]



        contest_candidate_collection.update_one(
            {
                "contest_id": contest_obj_id,
                "candidate_id": candidate_id
            },
            {
                "$set": {
                    "hr.start_time": start_time,
                    "hr.question_bank":question_bank
                }
            }
        )



    if schedule_autosubmit:
        asyncio.create_task(
            auto_submit(
                contest_id,
                token,
                start_time,
                contest["hr_round"]["end"],
                contest["hr_round"]["duration"],
                submit_hr
            )
        )

    
    return {
        "success": True,
        "questions": hr_questions,
        "duration": contest["hr_round"]["duration"],
        "start_time": start_time
    }






@router.post("/hr/answer")
async def submit_hr_answer(
    contest_id: str = Form(...),
    question_id: str = Form(...),
    frontend_timestamp: datetime = Form(...),
    audio: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    
    backend_timestamp = generate_timestamp()
    timestamp = verify_timestamp(frontend_timestamp, backend_timestamp)
    

    token = credentials.credentials
    payload = verify_access_token(token)

    candidate, candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")
    verify_candidate_passed_concept(candidate_id, contest_id)
    verify_hr_question(contest, question_id)
    verify_hr_time(timestamp, contest, contest_candidate)
    verify_hr_submit(contest_candidate)


    if not audio.filename.lower().endswith(".wav"):
        raise HTTPException(
            status_code=400,
            detail="Only WAV audio files are accepted"
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:

        audio_bytes = await audio.read()
        temp_audio.write(audio_bytes)

        temp_audio_path = temp_audio.name

    segmented_data , transcript = call_audio_model_1(temp_audio_path)

    with open(temp_audio_path, "rb") as f:
        audio_file_id = contest_audio_fs.put(
            f,
            filename=audio.filename,
            content_type=audio.content_type
        )

    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id,
            "hr.question_bank.question_id": question_id
        },
        {
            "$set": {
                "hr.question_bank.$.audio_id": audio_file_id,
                "hr.question_bank.$.transcript": transcript,
                "hr.question_bank.$.segmented_data": segmented_data,
                "hr.question_bank.$.timestamp": timestamp,
                "hr.question_bank.$.score": None
            }
        }
    )

    return {
        "success": True,
        "message": "Answer saved"
    }









@router.get("/leaderboard/hr")
def get_hr_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    candidate, real_candidate_id, email = verify_candidate_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    contest_candidate = verify_contest_registry(candidate, contest, "Y")


    timestamp = generate_timestamp()
    verify_hr_result_time(timestamp, contest)


    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {"hr_round": 1, "_id": 0, "selected_hr_candidates":1}
    )

    if not leaderboard_doc:
        raise HTTPException(status_code=404, detail="Leaderboard not generated")

    leaderboard = leaderboard_doc["hr_round"]
    candidate_ids = [entry["candidate_id"] for entry in leaderboard]


    candidates = list(
        candidate_collection.find(
            {"_id": {"$in": candidate_ids}},
            {"_id": 1, "full_name": 1}
        )
    )
    name_map = {
        c["_id"]: c["full_name"]
        for c in candidates
    }

    result = []
    for entry in leaderboard:
        result.append({
            "candidate_id": str(real_candidate_id) if real_candidate_id == entry["candidate_id"] else None,
            "name": name_map.get(entry["candidate_id"], "Unknown"),
            "rank": entry["rank"],
            "percentile": entry["percentile"],
            "score": entry["final_normalized_score"],
            "latest_submission": entry["latest_submission"]
        })

    if real_candidate_id in leaderboard_doc["selected_hr_candidates"]:
        selection = True
    else:
        selection = False




    return {
        "success": True,
        "data": result,
        "selection": selection
    }







