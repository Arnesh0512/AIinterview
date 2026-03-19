import asyncio
from bson import ObjectId
from datetime import timedelta, datetime
from utils.time import generate_timestamp
import inspect
from typing import Callable, Awaitable, Union
from database import contest_candidate_collection, leetcode, contest_collection
from prompt.contest import evaluate_coding_score, evaluate_concept_score, evaluate_hr_score
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


async def auto_submit(
    contest_id: str,
    token: str,
    end_time: datetime,
    fun: Union[
    Callable[[str, datetime, HTTPAuthorizationCredentials], None],
    Callable[[str, datetime, HTTPAuthorizationCredentials], Awaitable[None]]
    ]    
):  
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )


    now = generate_timestamp()
    wait_seconds = (end_time - now).total_seconds()

    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    if inspect.iscoroutinefunction(fun):
        await fun(contest_id, end_time, credentials)
    else:
        fun(contest_id, end_time, credentials)





def generate_coding_scores(contest_obj_id: ObjectId, candidate_id: ObjectId, contest_candidate):



    coding = contest_candidate.get("coding")
    question_bank = coding.get("question_bank", [])


    question_ids = [q["question_id"] for q in question_bank]

    questions = list(
        leetcode.find(
            {"_id": {"$in": question_ids}},
            {"_id": 1, "problem_description": 1}
        )
    )

    question_map = {
        q["_id"]: q["problem_description"]
        for q in questions
    }

    evaluation_input = []

    for q in question_bank:

        qid = q["question_id"]

        evaluation_input.append({
            "question_id": str(qid),
            "problem_description": question_map.get(qid, ""),
            "answer": q.get("answer") or "",
            "language": q.get("language") or ""
        })

    response = evaluate_coding_score(evaluation_input)

    results = response["results"]
    overall_feedback = response["overall_feedback"]

    score_map = {
        ObjectId(s["question_id"]): s["score"]
        for s in results
    }

    feedback_map = {
        ObjectId(f["question_id"]): f["feedback"]
        for f in results
    }

    new_question_bank = []

    for q in question_bank:

        qid = q["question_id"]

        new_question_bank.append({
            "question_id": qid,
            "language": q.get("language"),
            "answer": q.get("answer"),
            "timestamp": q.get("timestamp"),
            "feedback": feedback_map.get(qid, ""),
            "score": score_map.get(qid, 0)
        })

    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id
        },
        {
            "$set": {
                "coding.question_bank": new_question_bank,
                "coding.overall_feedback": overall_feedback
            }
        }
    )










def generate_concept_scores(contest_obj_id: ObjectId, candidate_id: ObjectId, contest_candidate):


    concept = contest_candidate.get("concept")
    question_bank = concept.get("question_bank", [])

    contest = contest_collection.find_one({"_id": contest_obj_id})
    concept_question_bank = contest["concept_round"]["questions"]


    evaluation_input = []

    for q in question_bank:

        qid = q["question_id"]

        evaluation_input.append({
            "question_id": qid,
            "question": concept_question_bank[qid],
            "answer": q.get("answer") or "",
        })

    response = evaluate_concept_score(evaluation_input)

    results = response["results"]
    overall_feedback = response["overall_feedback"]

    score_map = {
        s["question_id"]: s["score"]
        for s in results
    }
    feedback_map = {
        f["question_id"]: f["feedback"]
        for f in results
    }

    new_question_bank = []

    for q in question_bank:

        qid = q["question_id"]

        new_question_bank.append({
            "question_id": qid,
            "answer": q.get("answer"),
            "timestamp": q.get("timestamp"),
            "feedback": feedback_map.get(qid, ""),
            "score": score_map.get(qid, 0)
        })

    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id
        },
        {
            "$set": {
                "concept.question_bank": new_question_bank,
                "concept.overall_feedback": overall_feedback
            }
        }
    )





def generate_hr_scores(contest_obj_id: ObjectId, candidate_id: ObjectId, contest_candidate):
    hr = contest_candidate.get("hr")
    question_bank = hr.get("question_bank", [])

    contest = contest_collection.find_one({"_id": contest_obj_id})
    hr_question_bank = contest["hr_round"]["questions"]


    evaluation_input = []

    for q in question_bank:

        qid = q["question_id"]

        evaluation_input.append({
            "question_id": qid,
            "question": hr_question_bank[qid],
            "transcript": q.get("transcript") or "",
            "segmented_data": q.get("segmented_data") or []
        })

    summary = contest_candidate["resume"]["summary"]

    response = evaluate_hr_score(evaluation_input, summary)

    results = response["results"]
    overall_feedback = response["overall_feedback"]

    score_map = {
        s["question_id"]: s["score"]
        for s in results
    }
    feedback_map = {
        f["question_id"]: f["feedback"]
        for f in results
    }

    new_question_bank = []

    for q in question_bank:

        qid = q["question_id"]

        new_question_bank.append({
            "question_id": qid,
            "audio_id": q.get("audio_id"),
            "transcript": q.get("transcript"),
            "segmented_data": q.get("segmented_data"),
            "timestamp": q.get("timestamp"),
            "feedback": feedback_map.get(qid, ""),
            "score": score_map.get(qid, 0)
        })

    contest_candidate_collection.update_one(
        {
            "contest_id": contest_obj_id,
            "candidate_id": candidate_id
        },
        {
            "$set": {
                "hr.question_bank": new_question_bank,
                "hr.overall_feedback": overall_feedback
            }
        }
    )
