import asyncio
from utils.time import generate_timestamp
from fastapi.security import HTTPAuthorizationCredentials
import inspect
from bson import ObjectId
from database import contest_candidate_collection, contest_collection, candidate_collection
from bson import ObjectId
import inspect
from utils.contest import generate_coding_scores, generate_concept_scores, generate_hr_scores




async def run_contest_scheduler(
    contest: dict,
    token: str,
    generate_hr_result,
    generate_coding_result,
    generate_resume_result, 
    generate_concept_result, 
    generate_leaderboard
):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )
    contest_id = str(contest["_id"])



    async def wait_until(target_time, fun):

        now = generate_timestamp()
        wait_seconds = (target_time - now).total_seconds()

        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

        if inspect.iscoroutinefunction(fun):
            await fun(contest_id, credentials)
        else:
            fun(contest_id, credentials)



    await wait_until(
        contest["resume_round"]["result"],
        generate_resume_result
    )
    await wait_until(
        contest["coding_round"]["result"],
        generate_coding_result
    )
    await wait_until(
        contest["concept_round"]["result"],
        generate_concept_result
    )
    await wait_until(
        contest["hr_round"]["result"],
        generate_hr_result
    )
    await wait_until(
        contest["leaderboard_declare_time"],
        generate_leaderboard
    )




def fake_submit_candidate_coding(
    contest_id: ObjectId,
    contest: dict
):
    fake_submit_ids = contest.get("fake_submit_coding", [])
    
    if fake_submit_ids:

        fake_contest_candidates = list(
            contest_candidate_collection.find(
                {
                    "contest_id": contest_id,
                    "candidate_id": {"$in": fake_submit_ids}
                },
                {
                    "_id": 0,
                    "candidate_id": 1,
                    "coding": 1
                }
            )
        )

        for contest_candidate in fake_contest_candidates:
            generate_coding_scores(
                contest_id, 
                contest_candidate["candidate_id"], 
                contest_candidate
            )

            contest_candidate_collection.update_one(
                {
                    "contest_id": contest_id,
                    "candidate_id": contest_candidate["candidate_id"]
                },
                {
                    "$set": {
                        "coding.submitted_at": contest_candidate["coding"]["end_time"]
                    }
                }
            )

    contest_collection.update_one(
            {"_id": contest_id},
            {"$set": {"fake_submit_coding": []}}
        )







def fake_submit_candidate_concept(
    contest_id: ObjectId,
    contest: dict
):
    fake_submit_ids = contest.get("fake_submit_concept", [])
    
    if fake_submit_ids:

        fake_contest_candidates = list(
            contest_candidate_collection.find(
                {
                    "contest_id": contest_id,
                    "candidate_id": {"$in": fake_submit_ids}
                },
                {
                    "_id": 0,
                    "candidate_id": 1,
                    "concept": 1
                }
            )
        )

        for contest_candidate in fake_contest_candidates:
            generate_concept_scores(
                contest_id, 
                contest_candidate["candidate_id"], 
                contest_candidate
            )

            contest_candidate_collection.update_one(
                {
                    "contest_id": contest_id,
                    "candidate_id": contest_candidate["candidate_id"]
                },
                {
                    "$set": {
                        "concept.submitted_at": contest_candidate["concept"]["end_time"]
                    }
                }
            )
    
    contest_collection.update_one(
            {"_id": contest_id},
            {"$set": {"fake_submit_concept": []}}
        )




def fake_submit_candidate_hr(
    contest_id: ObjectId,
    contest: dict
):
    fake_submit_ids = contest.get("fake_submit_hr", [])
    
    if fake_submit_ids:

        fake_contest_candidates = list(
            contest_candidate_collection.find(
                {
                    "contest_id": contest_id,
                    "candidate_id": {"$in": fake_submit_ids}
                },
                {
                    "_id": 0,
                    "candidate_id": 1,
                    "hr": 1
                }
            )
        )

        for contest_candidate in fake_contest_candidates:
            generate_hr_scores(
                contest_id, 
                contest_candidate["candidate_id"], 
                contest_candidate
            )

            contest_candidate_collection.update_one(
                {
                    "contest_id": contest_id,
                    "candidate_id": contest_candidate["candidate_id"]
                },
                {
                    "$set": {
                        "hr.submitted_at": contest_candidate["hr"]["end_time"]
                    }
                }
            )
    
    contest_collection.update_one(
            {"_id": contest_id},
            {"$set": {"fake_submit_hr": []}}
        )








def format_leaderboard(entries):
    candidate_ids = [entry["candidate_id"] for entry in entries]

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

    return [
        {
            "candidate_id": str(entry["candidate_id"]),
            "name": candidate_map.get(entry["candidate_id"], {}).get("name"),
            "email": candidate_map.get(entry["candidate_id"], {}).get("email"),
            "rank": entry.get("rank"),
            "percentile": entry.get("percentile"),
            "score": entry.get("final_normalized_score"),
            "latest_submission": entry.get("latest_submission")
        }
        for entry in entries
    ]
