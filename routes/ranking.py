from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
from collections import defaultdict
import math

router = APIRouter(prefix="/ranking", tags=["Contest Ranking"])


# ============================================================
# Request Model
# ============================================================

class RankingRequest(BaseModel):
    users_scores: List[List[Dict[str, Any]]]
    """
    [
        [ {user_id, raw_score, submitted_at}, ... ],  # Question 1
        [ {user_id, raw_score, submitted_at}, ... ],  # Question 2
        [ {user_id, raw_score, submitted_at}, ... ],  # Question 3
    ]
    """


# ============================================================
# Core Normalization Logic
# ============================================================

def normalize_and_rank(users_scores):

    results = defaultdict(lambda: {
        "final_normalized_score": 0.0,
        "latest_submission": None
    })

    for question_data in users_scores:

        if not question_data:
            continue

        raw_scores = [entry["raw_score"] for entry in question_data]
        n = len(raw_scores)

        mean = sum(raw_scores) / n
        variance = sum((x - mean) ** 2 for x in raw_scores) / n
        std_dev = math.sqrt(variance)

        # If all scores equal → z-score = 0
        if std_dev == 0:
            for entry in question_data:
                user_id = entry["user_id"]
                submitted_time = parse_time(entry["submitted_at"])

                prev_time = results[user_id]["latest_submission"]
                if prev_time is None or submitted_time > prev_time:
                    results[user_id]["latest_submission"] = submitted_time
            continue

        for entry in question_data:
            user_id = entry["user_id"]
            raw_score = entry["raw_score"]

            z_score = (raw_score - mean) / std_dev
            results[user_id]["final_normalized_score"] += z_score

            submitted_time = parse_time(entry["submitted_at"])
            prev_time = results[user_id]["latest_submission"]

            if prev_time is None or submitted_time > prev_time:
                results[user_id]["latest_submission"] = submitted_time

    # Build leaderboard
    leaderboard = []

    for user_id, data in results.items():
        leaderboard.append({
            "user_id": user_id,
            "final_normalized_score": round(data["final_normalized_score"], 6),
            "latest_submission": data["latest_submission"]
        })

    # Sort:
    # 1️⃣ Higher normalized score first
    # 2️⃣ Earlier submission wins tie
    leaderboard.sort(
        key=lambda x: (
            -x["final_normalized_score"],
            x["latest_submission"]
        )
    )

    # Assign ranks + percentile
    total_users = len(leaderboard)
    current_rank = 1

    for i, user in enumerate(leaderboard):

        if i > 0 and (
            user["final_normalized_score"] == leaderboard[i - 1]["final_normalized_score"] and
            user["latest_submission"] == leaderboard[i - 1]["latest_submission"]
        ):
            user["rank"] = leaderboard[i - 1]["rank"]
        else:
            user["rank"] = current_rank

        current_rank += 1

        user["percentile"] = round(
            ((total_users - user["rank"]) / total_users) * 100,
            2
        )

        # Convert datetime to ISO string for JSON response
        if isinstance(user["latest_submission"], datetime):
            user["latest_submission"] = user["latest_submission"].isoformat()

    return leaderboard


def parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


# ============================================================
# Ranking Route
# ============================================================

@router.post("/contest")
def rank_users(data: RankingRequest):

    if not data.users_scores:
        raise HTTPException(status_code=400, detail="users_scores cannot be empty")

    try:
        leaderboard = normalize_and_rank(data.users_scores)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ranking failed: {str(e)}")

    return {
        "total_users": len(leaderboard),
        "leaderboard": leaderboard
    }