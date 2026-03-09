from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import admin_collection, contest_candidate_collection, contest_leaderboard
from schemas.user import UserCreate
from verify.token import verify_access_token
from verify.admin import verify_admin_payload, validate_contest_data, verify_contest_id, verify_duplicate_contest
from prompt.admin import validate_role_skills, generate_resume_questions, generate_concept_questions, generate_hr_questions
from utils.admin import generate_coding_ids
import json
from database import contest_collection
from schemas.contest import ContestCreate
from utils.time import generate_timestamp
from datetime import datetime, timezone
import asyncio
from utils.normalizer import normalize_and_rank, finalize_leaderboard
from bson import ObjectId
import inspect


security = HTTPBearer()

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)



@router.patch("/register")
def register_admin(
    admin_data: UserCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):


    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)
    if len(admin)>4:
        raise HTTPException(status_code=404, detail="admin Already Registered")

    update_data = admin_data.model_dump(mode="json")


    if email != update_data["email"].lower():
        raise HTTPException(
            status_code=400,
            detail="Email mismatch"
        )
    

    admin_collection.update_one(
        {"_id": admin_id},
        {"$set": update_data}
    )

    return {
        "success": True,
        "message": "admin registered successfully"
    }



@router.put("/change-details")
def change_admin_details(
    admin_data: UserCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    admin, admin_id, email = verify_admin_payload(payload)


    update_data = admin_data.model_dump(mode="json")

    if email != update_data["email"].lower():
        raise HTTPException(
            status_code=400,
            detail="Email mismatch"
        )

    admin_collection.update_one(
        {"_id": admin_id},
        {"$set": update_data}
    )

    return {
        "success": True,
        "message": "admin details updated successfully"
    }



@router.get("/profile")
def get_admin_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)

    admin, admin_id, email = verify_admin_payload(payload)


    admin["_id"] = str(admin["_id"])

    return {
        "success": True,
        "data": admin
    }










@router.post("/create-contest")
def create_contest(
    data: ContestCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)
    verify_duplicate_contest(data)


    validate_contest_data(data)
    validate_role_skills(
    data.role.value,
    [s.value for s in data.skills]
    )

    resume_questions = generate_resume_questions(
        data.company.value,
        data.role.value,
        [s.value for s in data.skills],
        data.resume_questions_count
    )
    resume_questions = {str(i + 1): q for i, q in enumerate(resume_questions)}

    coding_questions = generate_coding_ids(
        data.company.value,
        data.coding_questions_count
    )

    concept_questions = generate_concept_questions(
        data.role.value,
        [s.value for s in data.skills],
        data.concept_questions_count
    )
    concept_questions = {str(i + 1): q for i, q in enumerate(concept_questions)}

    hr_questions = generate_hr_questions(
        data.role.value,
        data.hr_questions_count-1
    )
    hr_questions = {str(i + 2): q for i, q in enumerate(hr_questions)}
    hr_questions["1"] = "Introduce Yourself"
    
    contest_data = data.model_dump()
    contest_data["admin_created_id"] = admin_id
    contest_data["skills"] = sorted([s.value for s in data.skills])
    contest_data["resume_round"]["questions"] = resume_questions
    contest_data["coding_round"]["questions"] = coding_questions
    contest_data["concept_round"]["questions"] = concept_questions
    contest_data["hr_round"]["questions"] = hr_questions
    contest_data["registered_candidates"] = []
    contest_data["candidate_count"] = 0
    contest_data["created_on"] = generate_timestamp()

    inserted = contest_collection.insert_one(contest_data)

    return {
        "success":True
    }


@router.get("/contest-ids")
def get_all_contest_ids(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contests = contest_collection.find(
        {},
        {
            "_id": 1,
            "company": 1,
            "role": 1,
            "skills": 1,
            "created_on": 1
        }
    )

    result = []

    for c in contests:
        result.append({
            "contest_id": str(c["_id"]),
            "company": c.get("company"),
            "role": c.get("role"),
            "skills": c.get("skills", []),
            "created_on": c.get("created_on")
        })

    return {
        "success": True,
        "data": result
    }


@router.get("/contest")
def get_contest_details(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, obj_id = verify_contest_id(contest_id)

    contest["_id"] = str(contest["_id"])
    contest["admin_created_id"] = str(contest["admin_created_id"])
    contest["coding_round"]["questions"] = [str(id) for id in contest["coding_round"]["questions"]]


    return {
        "success": True,
        "data": contest
    }








@router.post("/result/resume")
async def generate_resume_result(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    contest, contest_obj_id = verify_contest_id(contest_id)

    candidates = list(
        contest_candidate_collection.find(
            {
                "contest_id": contest_obj_id,
                "resume": {"$exists": True}
            },
            {
                "_id": 0,
                "candidate_id": 1,
                "resume.question_bank": 1,
                "resume.submitted_at": 1
            }
        )
    )

    if not candidates:
        raise ValueError("No resumes submitted for this contest")

    question_count = contest["resume_questions_count"]

    # initialize question-wise container
    candidates_scores = [[] for _ in range(question_count)]
    submitted_at = contest["resume_round"]["start"]


    for candidate in candidates:

        candidate_id = candidate["candidate_id"]
        question_bank = candidate["resume"]["question_bank"]

        for q in question_bank:

            qid = int(q["question_id"]) - 1
            score = q["score"]

            candidates_scores[qid].append({
                "candidate_id": str(candidate_id),
                "raw_score": score,
                "submitted_at": submitted_at
            })

    leaderboard = normalize_and_rank(candidates_scores)

    resume_leaderboard = []

    for entry in leaderboard:

        resume_leaderboard.append({
            "candidate_id": ObjectId(entry["candidate_id"]),
            "final_normalized_score": entry["final_normalized_score"],
            "latest_submission": entry["latest_submission"],
            "rank": entry["rank"],
            "percentile": entry["percentile"]
        })

    # top X candidates
    x = contest.get("selected_resume", 0)

    selected_resume_candidates = [
        entry["candidate_id"]
        for entry in resume_leaderboard[:x]
    ]

    contest_leaderboard.update_one(
        {"contest_id": contest_obj_id},
        {
            "$set": {
                "resume_round": resume_leaderboard,
                "selected_resume_candidates": selected_resume_candidates
            }
        },
        upsert=True
    )

    return


@router.post("/result/coding")
async def generate_coding_result(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    contest, contest_obj_id = verify_contest_id(contest_id)

    coding_ids = contest["coding_round"]["questions"]
    contest_start = contest["coding_round"]["start"]

    coding_ids_map = {qid: i for i, qid in enumerate(coding_ids)}

    candidates = list(
        contest_candidate_collection.find(
            {
                "contest_id": contest_obj_id,
                "coding": {"$exists": True}
            },
            {
                "_id": 0,
                "candidate_id": 1,
                "coding.question_bank": 1,
                "coding.start_time": 1
            }
        )
    )

    if not candidates:
        raise ValueError("No codings submitted for this contest")

    question_count = len(coding_ids)
    candidates_scores = [[] for _ in range(question_count)]

    for candidate in candidates:

        candidate_id = candidate["candidate_id"]
        coding = candidate.get("coding", {})
        start_time = coding.get("start_time")
        question_bank = coding.get("question_bank", [])

        qb_map = {q["question_id"]: q for q in question_bank}

        for qid in coding_ids:

            q = qb_map.get(qid)

            if q["score"] is None:
                score = 0
            else:
                score = q["score"]


            if q["timestamp"] is None or start_time is None:
                timestamp = datetime.max.replace(tzinfo=timezone.utc)
            else:
                timestamp = contest_start + q["timestamp"] - start_time

            index = coding_ids_map[qid]

            candidates_scores[index].append({
                "candidate_id": str(candidate_id),
                "raw_score": score,
                "submitted_at": timestamp
            })

    leaderboard = normalize_and_rank(candidates_scores)

    coding_leaderboard = []

    for entry in leaderboard:
        coding_leaderboard.append({
            "candidate_id": ObjectId(entry["candidate_id"]),
            "final_normalized_score": entry["final_normalized_score"],
            "latest_submission": entry["latest_submission"],
            "rank": entry["rank"],
            "percentile": entry["percentile"]
        })

    x = contest.get("selected_coding", 0)

    selected_coding_candidates = [
        entry["candidate_id"]
        for entry in coding_leaderboard[:x]
    ]

    contest_leaderboard.update_one(
        {"contest_id": contest_obj_id},
        {
            "$set": {
                "coding_round": coding_leaderboard,
                "selected_coding_candidates": selected_coding_candidates
            }
        },
        upsert=True
    )


@router.post("/result/concept")
async def generate_concept_result(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    contest, contest_obj_id = verify_contest_id(contest_id)

    concept_ids = list(contest["concept_round"]["questions"].keys())
    contest_start = contest["concept_round"]["start"]
    concept_index_map = {qid: i for i, qid in enumerate(concept_ids)}


    candidates = list(
        contest_candidate_collection.find(
            {
                "contest_id": contest_obj_id,
                "concept": {"$exists": True}
            },
            {
                "_id": 0,
                "candidate_id": 1,
                "concept.question_bank": 1,
                "concept.start_time": 1
            }
        )
    )

    if not candidates:
        raise ValueError("No concepts submitted for this contest")

    question_count = len(concept_ids)

    # initialize question-wise container
    candidates_scores = [[] for _ in range(question_count)]
    submitted_at = contest["concept_round"]["start"]


    for candidate in candidates:

        candidate_id = candidate["candidate_id"]
        concept = candidate.get("concept", {})
        start_time = concept.get("start_time")
        question_bank = concept.get("question_bank", [])

        

        qb_map = {q["question_id"]: q for q in question_bank}

        for qid in concept_ids:

            q = qb_map.get(qid)

            if q["score"] is None:
                score = 0
            else:
                score = q["score"]


            if q["timestamp"] is None or start_time is None:
                timestamp = datetime.max.replace(tzinfo=timezone.utc)
            else:
                timestamp = contest_start + q["timestamp"] - start_time


            index = concept_index_map[qid]

            candidates_scores[index].append({
                "candidate_id": str(candidate_id),
                "raw_score": score,
                "submitted_at": timestamp
            })

    leaderboard = normalize_and_rank(candidates_scores)

    concept_leaderboard = []

    for entry in leaderboard:

        concept_leaderboard.append({
            "candidate_id": ObjectId(entry["candidate_id"]),
            "final_normalized_score": entry["final_normalized_score"],
            "latest_submission": entry["latest_submission"],
            "rank": entry["rank"],
            "percentile": entry["percentile"]
        })

    # top X candidates
    x = contest.get("selected_concept", 0)

    selected_concept_candidates = [
        entry["candidate_id"]
        for entry in concept_leaderboard[:x]
    ]

    contest_leaderboard.update_one(
        {"contest_id": contest_obj_id},
        {
            "$set": {
                "concept_round": concept_leaderboard,
                "selected_concept_candidates": selected_concept_candidates
            }
        },
        upsert=True
    )

    return


@router.post("/result/hr")
async def generate_hr_result(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    contest, contest_obj_id = verify_contest_id(contest_id)

    hr_ids = list(contest["hr_round"]["questions"].keys())
    contest_start = contest["hr_round"]["start"]
    hr_index_map = {qid: i for i, qid in enumerate(hr_ids)}


    candidates = list(
        contest_candidate_collection.find(
            {
                "contest_id": contest_obj_id,
                "hr": {"$exists": True}
            },
            {
                "_id": 0,
                "candidate_id": 1,
                "hr.question_bank": 1,
                "hr.start_time": 1
            }
        )
    )

    if not candidates:
        raise ValueError("No hrs submitted for this contest")

    question_count = len(hr_ids)

    # initialize question-wise container
    candidates_scores = [[] for _ in range(question_count)]
    submitted_at = contest["hr_round"]["start"]


    for candidate in candidates:

        candidate_id = candidate["candidate_id"]
        hr = candidate.get("hr", {})
        start_time = hr.get("start_time")
        question_bank = hr.get("question_bank", [])

        

        qb_map = {q["question_id"]: q for q in question_bank}

        for qid in hr_ids:

            q = qb_map.get(qid)

            if q["score"] is None:
                score = 0
            else:
                score = q["score"]


            if q["timestamp"] is None or start_time is None:
                timestamp = datetime.max.replace(tzinfo=timezone.utc)
            else:
                timestamp = contest_start + q["timestamp"] - start_time


            index = hr_index_map[qid]

            candidates_scores[index].append({
                "candidate_id": str(candidate_id),
                "raw_score": score,
                "submitted_at": timestamp
            })

    leaderboard = normalize_and_rank(candidates_scores)

    hr_leaderboard = []

    for entry in leaderboard:

        hr_leaderboard.append({
            "candidate_id": ObjectId(entry["candidate_id"]),
            "final_normalized_score": entry["final_normalized_score"],
            "latest_submission": entry["latest_submission"],
            "rank": entry["rank"],
            "percentile": entry["percentile"]
        })

    # top X candidates
    x = contest.get("selected_hr", 0)

    selected_hr_candidates = [
        entry["candidate_id"]
        for entry in hr_leaderboard[:x]
    ]

    contest_leaderboard.update_one(
        {"contest_id": contest_obj_id},
        {
            "$set": {
                "hr_round": hr_leaderboard,
                "selected_hr_candidates": selected_hr_candidates
            }
        },
        upsert=True
    )

    return




def generate_leaderboard(contest_id):

    contest, contest_obj_id = verify_contest_id(contest_id)

    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {
            "_id": 0,
            "resume_round": 1,
            "coding_round": 1,
            "concept_round": 1,
            "hr_round": 1
        }
    )

    if not leaderboard_doc:
        raise ValueError("No round leaderboards found")

    section_outputs = []

    def convert_section(section):

        converted = []

        for entry in section:

            converted.append({
                "candidate_id": str(entry["candidate_id"]),
                "final_normalized_score": entry["final_normalized_score"],
                "latest_submission": entry["latest_submission"]
            })

        return converted

    if leaderboard_doc.get("resume_round"):
        section_outputs.append(convert_section(leaderboard_doc["resume_round"]))

    if leaderboard_doc.get("coding_round"):
        section_outputs.append(convert_section(leaderboard_doc["coding_round"]))

    if leaderboard_doc.get("concept_round"):
        section_outputs.append(convert_section(leaderboard_doc["concept_round"]))

    if leaderboard_doc.get("hr_round"):
        section_outputs.append(convert_section(leaderboard_doc["hr_round"]))

    if not section_outputs:
        raise ValueError("No section leaderboards available")

    final_leaderboard = finalize_leaderboard(section_outputs)

    formatted = []

    for entry in final_leaderboard:

        formatted.append({
            "candidate_id": ObjectId(entry["candidate_id"]),
            "final_normalized_score": entry["final_normalized_score"],
            "latest_submission": entry["latest_submission"],
            "rank": entry["rank"],
            "percentile": entry["percentile"]
        })

    contest_leaderboard.update_one(
        {"contest_id": contest_obj_id},
        {
            "$set": {
                "final_leaderboard": formatted
            }
        },
        upsert=True
    )

    return formatted






async def wait_until(target_time):

    now = generate_timestamp()
    wait_seconds = (target_time - now).total_seconds()

    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)


async def run_contest_scheduler(
    contest: dict,
    token: str,
):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )
    contest_id = str(contest["_id"])

    await wait_until(contest["resume_round"]["result"])
    fun = generate_resume_result
    if inspect.iscoroutinefunction(fun):
        await fun(contest_id, credentials)
    else:
        fun(contest_id, credentials)



    await wait_until(contest["coding_round"]["result"])
    fun = generate_coding_result
    if inspect.iscoroutinefunction(fun):
        await fun(contest_id, credentials)
    else:
        fun(contest_id, credentials)




    await wait_until(contest["concept_round"]["result"])
    fun = generate_concept_result
    if inspect.iscoroutinefunction(fun):
        await fun(contest_id, credentials)
    else:
        fun(contest_id, credentials)




    await wait_until(contest["hr_round"]["result"])
    fun = generate_hr_result
    if inspect.iscoroutinefunction(fun):
        await fun(contest_id, credentials)
    else:
        fun(contest_id, credentials)





    await wait_until(contest["leaderboard_declare_time"])
    fun = generate_leaderboard
    if inspect.iscoroutinefunction(fun):
        await fun(contest_id, credentials)
    else:
        fun(contest_id, credentials)


@router.post("/start-contest")
async def start_contest(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)

    asyncio.create_task(run_contest_scheduler(contest))

    return {
        "success": True,
        "message": "Contest scheduler started"
    }