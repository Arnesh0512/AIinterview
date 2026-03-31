from datetime import datetime
from collections import defaultdict

''' INPUT: 
section1 = [
    {"user_id": "u1", "final_normalized_score": 1.5, "latest_submission": datetime(2026,2,26,10,15), "rank": 1, "percentile": 50},
    {"user_id": "u2", "final_normalized_score": 0.5, "latest_submission": datetime(2026,2,26,10,20), "rank": 2, "percentile": 0},
]

section2 = [
    {"user_id": "u1", "final_normalized_score": 2.0, "latest_submission": datetime(2026,2,26,10,25), "rank": 1, "percentile": 50},
    {"user_id": "u2", "final_normalized_score": 1.0, "latest_submission": datetime(2026,2,26,10,28), "rank": 2, "percentile": 0},
]

'''

def finalize_leaderboard(section_outputs):

    cumulative = defaultdict(lambda: {
        "final_normalized_score": 0.0,
        "latest_submission": None
    })

    # Step 1: Accumulate final_normalized_score & track latest submission per user
    for section in section_outputs:
        for entry in section:
            user_id = entry["user_id"]
            cumulative[user_id]["final_normalized_score"] += entry["final_normalized_score"]

            submitted_time = entry["latest_submission"]
            prev_time = cumulative[user_id]["latest_submission"]

            # Latest submission across sections (for tie-break)
            if prev_time is None or submitted_time > prev_time:
                cumulative[user_id]["latest_submission"] = submitted_time

    # Step 2: Create list for ranking
    leaderboard = []
    for user_id, data in cumulative.items():
        leaderboard.append({
            "user_id": user_id,
            "final_normalized_score": data["final_normalized_score"],
            "latest_submission": data["latest_submission"]
        })

    # Step 3: Sort leaderboard
    # Higher score first, tie-break with earlier latest_submission
    leaderboard.sort(key=lambda x: (-x["final_normalized_score"], x["latest_submission"]))

    # Step 4: Assign rank and percentile
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

        # Percentile formula (0-100 scale)
        user["percentile"] = ((total_users - user["rank"]) / total_users) * 100

    return leaderboard


# sections = [[
#     {"user_id": "u1", "final_normalized_score": 1.5, "latest_submission": datetime(2026,2,26,10,15), "rank": 1, "percentile": 50},
#     {"user_id": "u2", "final_normalized_score": 0.5, "latest_submission": datetime(2026,2,26,10,20), "rank": 2, "percentile": 0},
# ],
# [
#     {"user_id": "u1", "final_normalized_score": 2.0, "latest_submission": datetime(2026,2,26,10,25), "rank": 1, "percentile": 50},
#     {"user_id": "u2", "final_normalized_score": 1.0, "latest_submission": datetime(2026,2,26,10,28), "rank": 2, "percentile": 0},
# ]]
#
# print(finalize_leaderboard(sections))
