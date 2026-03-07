from bson import ObjectId
from database import coding_question_collection, leetcode, coding_collection
from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from typing import Callable, Awaitable, Union
import asyncio
from fastapi.security import HTTPAuthorizationCredentials
import inspect
from utils.time import generate_timestamp


def get_used_coding_question_ids(coding_id: ObjectId):

    used_questions = set()

    sessions = coding_question_collection.find(
        {"coding_id": coding_id},
        {"question_bank.question_id": 1}
    )

    for session in sessions:
        for q in session.get("question_bank", []):
            qid = q.get("question_id")
            if qid:
                used_questions.add(qid)

    return list(used_questions)


def previous_coding_session_questions(
    coding_id: ObjectId,
    x: int = None,
    session_number: int = None
):
    session_dict = {}
    sessions_used = {}

    search_query = {
        "coding_id": coding_id,
        "status": "passive"
        }

    if session_number is not None:
        search_query["session_number"] = session_number

    sessions = list(
        coding_question_collection.find(
            search_query,
            {
                "_id": 1,
                "session_number": 1,
                "question_bank": 1,
                "timestamp": 1
            }
        ).sort("timestamp", -1)
    )


    if session_number is None:
        latest_sessions = {}
        for s in sessions:
            sn = s["session_number"]
            if sn not in latest_sessions:
                latest_sessions[sn] = s
        sessions = list(latest_sessions.values())

    if x:
        sessions = sessions[:x]
    if len(sessions) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Need at least 2 sessions for combined feedback."
        )


    question_ids = set()
    if session_number:
        sessions_diff = [sessions[0]]
    else:
        sessions_diff = sessions

    for s in sessions_diff:
        for q in s.get("question_bank", []):
            if q.get("answer") and q.get("question_id"):
                question_ids.add(q["question_id"])

    problems = list(
        leetcode.find(
            {"question_id": {"$in": list(question_ids)}},
            {"question_id": 1, "problem_description": 1}
        )
    )

    problem_map = {
        p["question_id"]: p["problem_description"]
        for p in problems
    }



    for idx, s in enumerate(sessions):
        sid = str(s["_id"])
        ts = s["timestamp"]
        sn = s["session_number"]

        formatted_questions = {}

        for q in s.get("question_bank", []):

            qid = q.get("question_id")
            answer = q.get("answer")
            language = q.get("language")

            if not answer or qid not in problem_map:
                continue

            problem_description = problem_map[qid]

            formatted_questions[f"{problem_description}"] = (
                f"""Language: {language}\n Answer:\n{answer}"""
            )

        session_dict[f"session_{idx+1}"] = formatted_questions

        sessions_used[str(ts)] = {
            "session_number": sn,
            "session_id": sid
        }

    return session_dict, sessions_used




async def auto_submit(
    coding_id: str,
    question_session_id: str,
    token: str,
    start_time : datetime,
    duration: int,
    fun: Union[
    Callable[[str, str, datetime, HTTPAuthorizationCredentials], None],
    Callable[[str, str, datetime, HTTPAuthorizationCredentials], Awaitable[None]]
    ]
):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )

    end_time = start_time + timedelta(seconds=duration) + timedelta(minutes=1)
    now = generate_timestamp()
    wait_seconds = (end_time - now).total_seconds()

    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    if inspect.iscoroutinefunction(fun):
        await fun(coding_id, question_session_id, generate_timestamp(), credentials)
    else:
        fun(coding_id, question_session_id, generate_timestamp(), credentials)


