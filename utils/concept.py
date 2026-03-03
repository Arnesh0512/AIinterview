from database import concept_question_collection
from bson import ObjectId
from fastapi import HTTPException

def previous_concept_session_questions(
    concept_id: ObjectId,
    x: int = None,
    session_number: int = None,
):
    
    session_dict = {}
    sessions_used = {}
    
    search_query = {"concept_id": concept_id}

    if session_number:
        search_query["session_number"] = session_number

    all_sessions = list(
        concept_question_collection.find(
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

