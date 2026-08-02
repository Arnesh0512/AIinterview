from datetime import datetime
from collections import defaultdict

def finalize_leaderboard(section_outputs):

    cumulative = defaultdict(lambda: {
        "final_normalized_score": 0.0,
        "latest_submission": None
    })

    # Step 1: Accumulate final_normalized_score & track latest submission per candidate
    for section in section_outputs:
        for entry in section:
            candidate_id = entry["candidate_id"]
            cumulative[candidate_id]["final_normalized_score"] += entry["final_normalized_score"]

            submitted_time = entry["latest_submission"]
            prev_time = cumulative[candidate_id]["latest_submission"]

            # Latest submission across sections (for tie-break)
            if prev_time is None or submitted_time > prev_time:
                cumulative[candidate_id]["latest_submission"] = submitted_time

    # Step 2: Create list for ranking
    leaderboard = []
    for candidate_id, data in cumulative.items():
        leaderboard.append({
            "candidate_id": candidate_id,
            "final_normalized_score": data["final_normalized_score"],
            "latest_submission": data["latest_submission"]
        })

    # Step 3: Sort leaderboard
    # Higher score first, tie-break with earlier latest_submission
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

        # Percentile formula (0-100 scale)
        candidate["percentile"] = ((total_candidates - candidate["rank"]) / total_candidates) * 100

    return leaderboard

'''
sections = [
    [#section 1 
        {"candidate_id": "u1", "final_normalized_score": 1.5, "latest_submission": datetime(2026,2,26,10,15), "rank": 1, "percentile": 50},
        {"candidate_id": "u2", "final_normalized_score": 0.5, "latest_submission": datetime(2026,2,26,10,20), "rank": 2, "percentile": 0},
    ],
    [#section 2
        {"candidate_id": "u1", "final_normalized_score": 2.0, "latest_submission": datetime(2026,2,26,10,25), "rank": 1, "percentile": 50},
        {"candidate_id": "u2", "final_normalized_score": 1.0, "latest_submission": datetime(2026,2,26,10,28), "rank": 2, "percentile": 0},
    ]
]

print(finalize_leaderboard(sections))

[
    {
        "candidate_id": "u1",
        "final_normalized_score": 3.5,  # 1.5 (section1) + 2.0 (section2)
        "latest_submission": datetime.datetime(2026, 2, 26, 10, 25),  # latest across sections
        "rank": 1,  # highest cumulative normalized score
        "percentile": 100.0  # top performer
    },
    {
        "candidate_id": "u2",
        "final_normalized_score": 1.5,  # 0.5 (section1) + 1.0 (section2)
        "latest_submission": datetime.datetime(2026, 2, 26, 10, 28),
        "rank": 2,
        "percentile": 0.0  # lowest performer
    }
]
'''