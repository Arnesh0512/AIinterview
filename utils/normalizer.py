from datetime import datetime
from collections import defaultdict
import math
'''
    """ INPUT::
    candidates_scores: List[List[Dict]]
    [
        [ {candidate_id, raw_score, submitted_at}, ... ],  # Q1
        [ {candidate_id, raw_score, submitted_at}, ... ],  # Q2
        ...
    ]

'''

def normalize_and_rank(candidates_scores):

    # Step 1: Normalize all questions and accumulate final z-score
    results = defaultdict(lambda: {
        "final_normalized_score": 0.0,
        "latest_submission": None
    })

    for question_data in candidates_scores:
        if not question_data:
            continue

        raw_scores = [entry["raw_score"] for entry in question_data]
        n = len(raw_scores)

        mean = sum(raw_scores) / n
        variance = sum((x - mean) ** 2 for x in raw_scores) / n
        std_dev = math.sqrt(variance)

        # If all same score → z = 0
        if std_dev == 0:
            for entry in question_data:
                candidate_id = entry["candidate_id"]
                submitted_time = (
                    entry["submitted_at"]
                    if isinstance(entry["submitted_at"], datetime)
                    else datetime.fromisoformat(entry["submitted_at"])
                )
                prev_time = results[candidate_id]["latest_submission"]
                if prev_time is None or submitted_time > prev_time:
                    results[candidate_id]["latest_submission"] = submitted_time
            continue

        # Compute z-score and accumulate
        for entry in question_data:
            candidate_id = entry["candidate_id"]
            raw_score = entry["raw_score"]
            z_score = (raw_score - mean) / std_dev
            results[candidate_id]["final_normalized_score"] += z_score

            submitted_time = (
                entry["submitted_at"]
                if isinstance(entry["submitted_at"], datetime)
                else datetime.fromisoformat(entry["submitted_at"])
            )
            prev_time = results[candidate_id]["latest_submission"]
            if prev_time is None or submitted_time > prev_time:
                results[candidate_id]["latest_submission"] = submitted_time

    # Step 2: Create a list for ranking
    leaderboard = []
    for candidate_id, data in results.items():
        leaderboard.append({
            "candidate_id": candidate_id,
            "final_normalized_score": data["final_normalized_score"],
            "latest_submission": data["latest_submission"]
        })

    # Step 3: Sort leaderboard
    # 1) Higher final score first
    # 2) Tie → earlier submission wins
    leaderboard.sort(key=lambda x: (-x["final_normalized_score"], x["latest_submission"]))

    # Step 4: Assign rank and percentile
    total_candidates = len(leaderboard)
    current_rank = 1

    for i, candidate in enumerate(leaderboard):
        if i > 0 and (
                candidate["final_normalized_score"] == leaderboard[i - 1]["final_normalized_score"] and
                candidate["latest_submission"] == leaderboard[i - 1]["latest_submission"]
        ):
            candidate["rank"] = leaderboard[i - 1]["rank"]
        else:
            candidate["rank"] = current_rank
        current_rank += 1

        # Percentile: higher rank = higher percentile
        candidate["percentile"] = ((total_candidates - candidate["rank"] + 1) / total_candidates) * 100

    return leaderboard
'''
candidates_scores = [
    [  # Question 1
        {"candidate_id": "u1", "raw_score": 80, "submitted_at": "2026-02-26T10:05:00"},
        {"candidate_id": "u2", "raw_score": 65, "submitted_at": "2026-02-26T10:07:00"},
    ],
    [  # Question 2
        {"candidate_id": "u1", "raw_score": 90, "submitted_at": "2026-02-26T10:15:00"},
        {"candidate_id": "u2", "raw_score": 85, "submitted_at": "2026-02-26T10:18:00"},
    ]
]
print(normalize_and_rank(candidates_scores))

[
    {
        "candidate_id": "u1",
        "final_normalized_score": 1.224744871391589,  # sum of z-scores for Q1+Q2+Q3
        "latest_submission": datetime.datetime(2026, 2, 26, 10, 25),
        "rank": 1,
        "percentile": 33.33333333333333
    },
    {
        "candidate_id": "u3",
        "final_normalized_score": 0.816496580927726,
        "latest_submission": datetime.datetime(2026, 2, 26, 10, 22),
        "rank": 2,
        "percentile": 0.0
    }
]

'''