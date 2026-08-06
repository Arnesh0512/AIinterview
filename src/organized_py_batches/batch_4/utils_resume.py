import fitz
import pytesseract
from pdf2image import convert_from_path
from bson import ObjectId
from database import resume_question_collection
from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from typing import Callable, Awaitable, Union
import asyncio
from fastapi.security import HTTPAuthorizationCredentials
import inspect
from utils.time import generate_timestamp


def extract_text_without_ocr(pdf_path):
    text = ""
    doc = fitz.open(pdf_path)
    for page in doc:
        text += page.get_text()
        
    return text


def extract_text_with_ocr(pdf_path):
    text = ""
    pages = convert_from_path(pdf_path, dpi=400)

    for page in pages:
        text += pytesseract.image_to_string(page)
        text += "\n"

    return text




def previous_resume_session_questions(
    resume_id: ObjectId,
    x: int = None,
    session_number: int = None,
):
    
    session_dict = {}
    sessions_used = {}
    
    search_query = {
        "resume_id": resume_id,
        "status": "passive"
        }

    if session_number:
        search_query["session_number"] = session_number

    all_sessions = list(
        resume_question_collection.find(
            search_query,
            {
                "_id": 1,
                "session_number": 1,
                "question_bank": 1,
                "timestamp": 1
            }
        ).sort("timestamp", -1)
    )


    if not session_number:
        latest_sessions = {}

        for session in all_sessions:
            sn = session["session_number"]

            if sn not in latest_sessions:
                latest_sessions[sn] = session
        
        all_sessions = latest_sessions.values()


    sorted_sessions = sorted(
        all_sessions,
        key=lambda s: s["timestamp"],
        reverse=True
    )

    if x:
        sorted_sessions = sorted_sessions[:x]
        
        if len(sorted_sessions) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Need at least 2 sessions for combined feedback."
            )

    for idx, s in enumerate(sorted_sessions):
        sn = s["session_number"]
        sid = str(s["_id"])
        ts = s["timestamp"]

        session_dict[f"session_{idx+1}"] = {
            q.get("question", ""): q.get("answer", "")
            for q in s.get("question_bank", [])
            if q.get("answer")
        }

        sessions_used[str(ts)] = {
            "session_number": sn,
            "session_id": sid
        }

    return session_dict, sessions_used



    


async def auto_submit(
    resume_id: str,
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

    end_time = start_time + timedelta(minutes=duration) + timedelta(minutes=1)
    now = generate_timestamp()
    wait_seconds = (end_time - now).total_seconds()

    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    if inspect.iscoroutinefunction(fun):
        await fun(resume_id, question_session_id, generate_timestamp(), credentials)
    else:
        fun(resume_id, question_session_id, generate_timestamp(), credentials)


