from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import admin_collection, contest_candidate_collection, contest_leaderboard
from schemas.user import UserCreate
from verify.token import verify_access_token
from verify.admin import verify_admin_payload, validate_contest_data, verify_contest_id, verify_duplicate_contest
from prompt.admin import validate_role_skills, generate_resume_questions, generate_concept_questions, generate_hr_questions
from prompt.admin import generate_coding_ids
from database import contest_collection
from schemas.contest import ContestCreate
from utils.time import generate_timestamp
from datetime import datetime, timezone, timedelta
import asyncio
from utils.normalizer import normalize_and_rank, finalize_leaderboard
from utils.admin import run_contest_scheduler, fake_submit_candidate_coding,fake_submit_candidate_concept,fake_submit_candidate_hr
from bson import ObjectId
from database import candidate_collection
from verify.contest import verify_resume_result_time, verify_hr_result_time,verify_coding_result_time, verify_concept_result_time, verify_leaderboard_declare_time, verify_contest_registry
from utils.admin import format_leaderboard
from verify.candidate import verify_candidate_by_id
from fastapi.responses import StreamingResponse
from database import contest_resume_fs, contest_audio_fs, candidate_collection
from verify.candidate import verify_candidate_by_id
from verify.contest import verify_resume_round_data, verify_hr_audio_answer, verify_hr_question


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
    contest_data["fake_submit_coding"] = []
    contest_data["fake_submit_concept"] = []
    contest_data["fake_submit_hr"] = []

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
            "candidate_capacity": c.get("candidate_capacity"),
            "contest_start": c.get("contest_start"),
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
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

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
        raise HTTPException(status_code=404, detail="No resumes submitted for this contest")


    question_count = contest["resume_questions_count"]

    # initialize question-wise container
    candidates_scores = [[] for _ in range(question_count)]


    for candidate in candidates:

        candidate_id = candidate["candidate_id"]
        question_bank = candidate["resume"]["question_bank"]

        for q in question_bank:

            qid = int(q["question_id"]) - 1
            score = q["score"]

            candidates_scores[qid].append({
                "candidate_id": str(candidate_id),
                "raw_score": score,
                "submitted_at": datetime.min.replace(tzinfo=timezone.utc)
            })

    all_candidates = contest["registered_candidates"]
    all_candidates_str = {str(cid) for cid in all_candidates}
    participated = {entry["candidate_id"] for entry in candidates_scores[0]}
    missing_candidates = all_candidates_str - participated

    for qid in range(question_count):

        min_score = min(entry["raw_score"] for entry in candidates_scores[qid])
        penalty_score = min_score - 1

        for cid in missing_candidates:
            candidates_scores[qid].append({
                "candidate_id": cid,
                "raw_score": penalty_score,
                "submitted_at": datetime.min.replace(tzinfo=timezone.utc) + timedelta(seconds=600)
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
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    fake_submit_candidate_coding(contest_obj_id, contest)

    coding_ids = contest["coding_round"]["questions"]

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
                "coding.question_bank.question_id": 1,
                "coding.question_bank.score": 1,
                "coding.question_bank.timestamp": 1,
                "coding.start_time": 1
            }
        )
    )

    if not candidates:
        raise HTTPException(status_code=404, detail="No codings submitted for this contest")


    question_count = len(coding_ids)
    candidates_scores = [[] for _ in range(question_count)]
    duration = contest["coding_round"]["duration"] * 2

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
                timestamp = datetime.min.replace(tzinfo=timezone.utc) + timedelta(seconds=duration)
            else:
                timestamp = (datetime.min + (q["timestamp"] - start_time)).replace(tzinfo=timezone.utc)

            index = coding_ids_map[qid]

            candidates_scores[index].append({
                "candidate_id": str(candidate_id),
                "raw_score": score,
                "submitted_at": timestamp
            })


    all_candidates = contest["registered_candidates"]
    all_candidates_str = {str(cid) for cid in all_candidates}
    participated = {entry["candidate_id"] for entry in candidates_scores[0]}
    missing_candidates = all_candidates_str - participated

    for qid in range(question_count):

        min_score = min(entry["raw_score"] for entry in candidates_scores[qid])
        penalty_score = min_score - 1

        for cid in missing_candidates:
            candidates_scores[qid].append({
                "candidate_id": cid,
                "raw_score": penalty_score,
                "submitted_at":  datetime.min.replace(tzinfo=timezone.utc) + timedelta(seconds=duration)
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
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    fake_submit_candidate_concept(contest_obj_id, contest)

    concept_ids = list(contest["concept_round"]["questions"].keys())
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
                "concept.question_bank.question_id": 1,
                "concept.question_bank.score": 1,
                "concept.question_bank.timestamp": 1,
                "concept.start_time": 1
            }
        )
    )

    if not candidates:
        raise HTTPException(status_code=404, detail="No concepts submitted for this contest")


    question_count = len(concept_ids)

    # initialize question-wise container
    candidates_scores = [[] for _ in range(question_count)]
    duration = contest["concept_round"]["duration"] * 2


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
                timestamp = datetime.min.replace(tzinfo=timezone.utc) + timedelta(seconds=duration)
            else:
                timestamp = (datetime.min + (q["timestamp"] - start_time)).replace(tzinfo=timezone.utc)


            index = concept_index_map[qid]

            candidates_scores[index].append({
                "candidate_id": str(candidate_id),
                "raw_score": score,
                "submitted_at": timestamp
            })

    all_candidates = contest["registered_candidates"]
    all_candidates_str = {str(cid) for cid in all_candidates}
    participated = {entry["candidate_id"] for entry in candidates_scores[0]}
    missing_candidates = all_candidates_str - participated

    for qid in range(question_count):

        min_score = min(entry["raw_score"] for entry in candidates_scores[qid])
        penalty_score = min_score - 1

        for cid in missing_candidates:
            candidates_scores[qid].append({
                "candidate_id": cid,
                "raw_score": penalty_score,
                "submitted_at": datetime.min.replace(tzinfo=timezone.utc) + timedelta(seconds=duration)
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
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)
    contest, contest_obj_id = verify_contest_id(contest_id)
    fake_submit_candidate_hr(contest_obj_id, contest)

    hr_ids = list(contest["hr_round"]["questions"].keys())
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
                "hr.question_bank.question_id": 1,
                "hr.question_bank.score": 1,
                "hr.question_bank.timestamp": 1,
                "hr.start_time": 1
            }
        )
    )

    if not candidates:
        raise HTTPException(status_code=404, detail="No HR submissions found for this contest")


    question_count = len(hr_ids)

    # initialize question-wise container
    candidates_scores = [[] for _ in range(question_count)]
    duration = contest["hr_round"]["duration"] * 2


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
                timestamp = datetime.min.replace(tzinfo=timezone.utc) + timedelta(seconds=duration)
            else:
                timestamp = (datetime.min + (q["timestamp"] - start_time)).replace(tzinfo=timezone.utc)


            index = hr_index_map[qid]

            candidates_scores[index].append({
                "candidate_id": str(candidate_id),
                "raw_score": score,
                "submitted_at": timestamp
            })


    all_candidates = contest["registered_candidates"]
    all_candidates_str = {str(cid) for cid in all_candidates}
    participated = {entry["candidate_id"] for entry in candidates_scores[0]}
    missing_candidates = all_candidates_str - participated

    for qid in range(question_count):

        min_score = min(entry["raw_score"] for entry in candidates_scores[qid])
        penalty_score = min_score - 1

        for cid in missing_candidates:
            candidates_scores[qid].append({
                "candidate_id": cid,
                "raw_score": penalty_score,
                "submitted_at": datetime.min.replace(tzinfo=timezone.utc) + timedelta(seconds=duration)
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





@router.post("/result/leaderboard")
async def generate_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)
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
        raise HTTPException(status_code=404, detail="No round leaderboards found")

    section_outputs = []
    timeMap = {}

    def convert_section(section):

        converted = []

        for entry in section:
            
            cid = str(entry["candidate_id"])
            diff = entry["latest_submission"].replace(tzinfo=timezone.utc) - datetime.min.replace(tzinfo=timezone.utc)
            timeMap[cid] = timeMap.get(cid, timedelta()) + diff
            converted.append({
                "candidate_id": cid,
                "final_normalized_score": entry["final_normalized_score"],
                "latest_submission": timeMap[cid]
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
        raise HTTPException(status_code=404, detail="No section leaderboards available")


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

    x = contest.get("selected_hr", 0)

    selected_candidates = [
        entry["candidate_id"]
        for entry in formatted[:x]
    ]

    contest_leaderboard.update_one(
        {"contest_id": contest_obj_id},
        {
            "$set": {
                "final_leaderboard": formatted,
                "selected_candidates": selected_candidates
            }
        },
        upsert=True
    )

    return




@router.post("/start-contest")
async def start_contest(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)

    asyncio.create_task(
        run_contest_scheduler(
            contest,
            token,
            generate_hr_result,
            generate_coding_result,
            generate_resume_result, 
            generate_concept_result, 
            generate_leaderboard
        )
    )

    return {
        "success": True,
        "message": "Contest scheduler started"
    }




@router.get("/contest/candidates")
def get_registered_candidates(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)

    contest_candidates = list(
        contest_candidate_collection.aggregate([
            {
                "$match": {"contest_id": contest_obj_id}
            },
            {
                "$project": {
                    "_id": 0,
                    "candidate_id": 1,
                    "resume": {"$ne": ["$resume", None]},
                    "coding": {"$ne": ["$coding", None]},
                    "concept": {"$ne": ["$concept", None]},
                    "hr": {"$ne": ["$hr", None]}
                }
            }
        ])
    )

    candidate_ids = [doc["candidate_id"] for doc in contest_candidates]

    candidates = list(
        candidate_collection.find(
            {"_id": {"$in": candidate_ids}},
            {"full_name": 1, "email": 1}
        )
    )

    candidate_map = {
        c["_id"]: {
            "name": c.get("full_name"),
            "email": c.get("email")
        }
        for c in candidates
    }

    data = []
    for cc in contest_candidates:
        meta = candidate_map.get(cc["candidate_id"], {})

        if cc["hr"]:
            last_round = "hr"
        elif cc["concept"]:
            last_round = "concept"
        elif cc["coding"]:
            last_round = "coding"
        elif cc["resume"]:
            last_round = "resume"
        else:
            last_round = None

        data.append({
            "candidate_id": str(cc["candidate_id"]),
            "name": meta.get("name"),
            "email": meta.get("email"),
            "last_round_participated": last_round
        })

    return {
        "success": True,
        "data": data
    }


@router.get("/leaderboard/resume")
def view_resume_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)
    verify_resume_result_time(generate_timestamp(), contest)

    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {"resume_round": 1, "_id": 0}
    )

    if not leaderboard_doc or "resume_round" not in leaderboard_doc:
        raise HTTPException(status_code=404, detail="Resume leaderboard not found")

    return {
        "success": True,
        "data": format_leaderboard(leaderboard_doc["resume_round"])
    }


@router.get("/leaderboard/coding")
def view_coding_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)
    verify_coding_result_time(generate_timestamp(), contest)

    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {"coding_round": 1, "_id": 0}
    )

    if not leaderboard_doc or "coding_round" not in leaderboard_doc:
        raise HTTPException(status_code=404, detail="Coding leaderboard not found")

    return {
        "success": True,
        "data": format_leaderboard(leaderboard_doc["coding_round"])
    }



@router.get("/leaderboard/concept")
def view_concept_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)
    verify_concept_result_time(generate_timestamp(), contest)

    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {"concept_round": 1, "_id": 0}
    )

    if not leaderboard_doc or "concept_round" not in leaderboard_doc:
        raise HTTPException(status_code=404, detail="Concept leaderboard not found")

    return {
        "success": True,
        "data": format_leaderboard(leaderboard_doc["concept_round"])
    }


@router.get("/leaderboard/hr")
def view_hr_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)
    verify_hr_result_time(generate_timestamp(), contest)

    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {"hr_round": 1, "_id": 0}
    )

    if not leaderboard_doc or "hr_round" not in leaderboard_doc:
        raise HTTPException(status_code=404, detail="HR leaderboard not found")

    return {
        "success": True,
        "data": format_leaderboard(leaderboard_doc["hr_round"])
    }


@router.get("/leaderboard/final")
def view_final_leaderboard(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)
    verify_leaderboard_declare_time(generate_timestamp(), contest)

    leaderboard_doc = contest_leaderboard.find_one(
        {"contest_id": contest_obj_id},
        {"final_leaderboard": 1, "_id": 0}
    )

    if not leaderboard_doc or "final_leaderboard" not in leaderboard_doc:
        raise HTTPException(status_code=404, detail="Final leaderboard not found")

    return {
        "success": True,
        "data": format_leaderboard(leaderboard_doc["final_leaderboard"])
    }




@router.get("/contest/candidate")
def get_candidate_contest_details(
    contest_id: str,
    candidate_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)
    candidate, candidate_obj_id, candidate_email = verify_candidate_by_id(candidate_id, "Y")

    contest_candidate = verify_contest_registry(candidate,contest,"Y")
    contest_candidate["_id"] = str(contest_candidate["_id"])
    contest_candidate["contest_id"] = str(contest_candidate["contest_id"])
    contest_candidate["candidate_id"] = str(contest_candidate["candidate_id"])

    if contest_candidate.get("resume"):
        contest_candidate["resume"].pop("file_id", None)

    if contest_candidate.get("hr"):
        for q in contest_candidate["hr"].get("question_bank", []):
            q.pop("audio_id", None)

    return {
        "success": True,
        "data": contest_candidate
    }








@router.get("/contest/candidate/resume")
def get_candidate_resume_file(
    contest_id: str,
    candidate_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)
    candidate, candidate_obj_id, candidate_email = verify_candidate_by_id(candidate_id, "Y")
    contest_candidate = verify_contest_registry(candidate,contest,"Y")

    verify_resume_result_time(generate_timestamp(), contest)
    resume = verify_resume_round_data(contest_candidate)
    file_id = resume["file_id"]

    try:
        grid_out = contest_resume_fs.get(file_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Resume file not found")

    return StreamingResponse(
        grid_out,
        media_type=grid_out.content_type or "application/pdf",
        headers={"Content-Disposition": f'inline; filename="{grid_out.filename}"'}
    )


@router.get("/contest/candidate/hr/audio")
def get_candidate_hr_audio(
    contest_id: str,
    candidate_id: str,
    question_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)
    candidate, candidate_obj_id, candidate_email = verify_candidate_by_id(candidate_id, "Y")
    contest_candidate = verify_contest_registry(candidate,contest,"Y")

    verify_hr_result_time(generate_timestamp(), contest)
    verify_hr_question(contest, question_id)
    question_data = verify_hr_audio_answer(contest_candidate, question_id)
    audio_id = question_data["audio_id"]

    try:
        grid_out = contest_audio_fs.get(audio_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Audio file not found")

    return StreamingResponse(
        grid_out,
        media_type=grid_out.content_type or "audio/wav",
        headers={"Content-Disposition": f'inline; filename="{grid_out.filename}"'}
    )


@router.delete("/contest/delete")
def delete_contest(
    contest_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    admin, admin_id, email = verify_admin_payload(payload)

    contest, contest_obj_id = verify_contest_id(contest_id)

    contest_candidates = list(
        contest_candidate_collection.find({"contest_id": contest_obj_id})
    )

    resume_file_ids = []
    audio_file_ids = []

    for cc in contest_candidates:
        resume = cc.get("resume")
        if resume and resume.get("file_id"):
            resume_file_ids.append(resume["file_id"])

        hr = cc.get("hr")
        if hr:
            for q in hr.get("question_bank", []):
                if q.get("audio_id"):
                    audio_file_ids.append(q["audio_id"])

    for file_id in resume_file_ids:
        try:
            contest_resume_fs.delete(file_id)
        except Exception:
            pass

    for audio_id in audio_file_ids:
        try:
            contest_audio_fs.delete(audio_id)
        except Exception:
            pass

    contest_candidate_collection.delete_many({"contest_id": contest_obj_id})
    contest_leaderboard.delete_one({"contest_id": contest_obj_id})
    contest_collection.delete_one({"_id": contest_obj_id})

    return {
        "success": True,
        "message": "Contest deleted successfully"
    }
