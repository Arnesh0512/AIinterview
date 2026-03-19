from database import contest_collection, contest_leaderboard, contest_candidate_collection
from fastapi import HTTPException
from bson import ObjectId
from bson.errors import InvalidId
from utils.time import generate_timestamp
from datetime import timezone, timedelta

def verify_contest_id(contest_id: str):

    try:
        obj_id = ObjectId(contest_id)
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail="Invalid contest_id"
        )

    contest = contest_collection.find_one({"_id": obj_id})

    if not contest:
        raise HTTPException(
            status_code=404,
            detail="Contest not found"
        )

    return contest, obj_id



def verify_candidate_eligibility(current_time, candidate, contest):

    


    if current_time > contest["last_date_to_register"]:
        raise HTTPException(
            status_code=400,
            detail="Registration closed"
        )

    if contest["candidate_count"] >= contest["candidate_capacity"]:
        raise HTTPException(
            status_code=400,
            detail="Contest capacity full"
        )

    candidate_roles = [r.value for r in candidate["roles"]]

    if contest["role"] not in candidate_roles:
        raise HTTPException(
            status_code=403,
            detail="Candidate role mismatch"
        )

    candidate_skills = [s.value for s in candidate["skills"]]

    if not any(skill in candidate_skills for skill in contest["skills"]):
        raise HTTPException(
            status_code=403,
            detail="Candidate skills mismatch"
        )
    
    
        

def verify_contest_registry(candidate, contest, type):

    if type == "N":
        if candidate["_id"] in contest["registered_candidates"]:
            raise HTTPException(
                status_code=400,
                detail="Already registered"
            )
        else:
            return None
        
    
    if type == "Y":
        if candidate["_id"] not in contest["registered_candidates"]:
            raise HTTPException(
                status_code=400,
                detail="Candidate not registered for contest"
            )
        else:
            contest_candidate = contest_candidate_collection.find_one(
                {
                    "contest_id": contest["_id"],
                    "candidate_id": candidate["_id"]
                }
            )
            return contest_candidate



def verify_resume_time_open(timestamp, contest):
    start = contest["resume_round"]["start"]
    end = contest["resume_round"]["end"]

    if timestamp <= start or timestamp >= end:
        raise HTTPException(
            status_code=400,
            detail="Resume submission window closed"
        )

def verify_coding_time_open(timestamp, contest):
    
    start = contest["coding_round"]["start"]
    end = contest["coding_round"]["end"]

    if timestamp <= start or timestamp >= end:
        raise HTTPException(
            status_code=400,
            detail="Coding submission window closed"
        )

def verify_concept_time_open(timestamp, contest):
    
    start = contest["concept_round"]["start"]
    end = contest["concept_round"]["end"]

    if timestamp <= start or timestamp >= end:
        raise HTTPException(
            status_code=400,
            detail="Concept submission window closed"
        )
    

def verify_hr_time_open(timestamp, contest):
    
    start = contest["hr_round"]["start"]
    end = contest["hr_round"]["end"]

    if timestamp <= start or timestamp >= end:
        raise HTTPException(
            status_code=400,
            detail="HR submission window closed"
        )

def verify_coding_time(timestamp, contest, contest_candidate):

    coding = contest_candidate.get("coding")

    if not coding:
        raise HTTPException(
            status_code=400,
            detail="Coding round not started"
        )


    start_time = contest_candidate["coding"]["start_time"]
    end_time = contest_candidate["coding"]["end_time"]

    if timestamp <= start_time or timestamp >= end_time:
        raise HTTPException(
            status_code=400,
            detail="Coding submission window closed"
        )


def verify_concept_time(timestamp, contest, contest_candidate):

    concept = contest_candidate.get("concept")

    if not concept:
        raise HTTPException(
            status_code=400,
            detail="concept round not started"
        )


    start_time = contest_candidate["concept"]["start_time"]
    end_time = contest_candidate["concept"]["end_time"]

    if timestamp <= start_time or timestamp >= end_time:
        raise HTTPException(
            status_code=400,
            detail="Concept submission window closed"
        )


def verify_hr_time(timestamp, contest, contest_candidate):

    hr = contest_candidate.get("hr")

    if not hr:
        raise HTTPException(
            status_code=400,
            detail="HR round not started"
        )


    start_time = contest_candidate["hr"]["start_time"]
    end_time = contest_candidate["hr"]["end_time"]

    if timestamp <= start_time or timestamp >= end_time:
        raise HTTPException(
            status_code=400,
            detail="HR submission window closed"
        )



def verify_timestamp(frontend_timestamp, backend_timestamp):



    if frontend_timestamp.tzinfo is not None:
        frontend_timestamp = frontend_timestamp.astimezone(timezone.utc)
    else:
        frontend_timestamp = frontend_timestamp.replace(tzinfo=timezone.utc)


    time_diff_seconds = abs((backend_timestamp - frontend_timestamp).total_seconds())

    if time_diff_seconds > 120:
        raise HTTPException(
            status_code=400,
            detail="Submission time mismatch exceeds 2 minutes"
        )
    
    return frontend_timestamp
    


def verify_resume_result_time(timestamp, contest):

    result_time = contest["resume_round"]["result"]

    if timestamp < result_time:
        raise HTTPException(
            status_code=403,
            detail="Resume results not declared yet"
        )
    

def verify_coding_result_time(timestamp, contest):

    result_time = contest["coding_round"]["result"]

    if timestamp < result_time:
        raise HTTPException(
            status_code=403,
            detail="Coding results not declared yet"
        )

def verify_concept_result_time(timestamp, contest):

    result_time = contest["concept_round"]["result"]

    if timestamp < result_time:
        raise HTTPException(
            status_code=403,
            detail="Concept results not declared yet"
        )

def verify_hr_result_time(timestamp, contest):

    result_time = contest["hr_round"]["result"]

    if timestamp < result_time:
        raise HTTPException(
            status_code=403,
            detail="HR results not declared yet"
        )

def verify_leaderboard_declare_time(timestamp, contest):

    result_time = contest["leaderboard_declare_time"]

    if timestamp < result_time:
        raise HTTPException(
            status_code=403,
            detail="Leaderboard not declared yet"
        )




def verify_candidate_passed_resume(candidate_id, contest_id):

    leaderboard = contest_leaderboard.find_one(
        {"contest_id": ObjectId(contest_id)},
        {"selected_resume_candidates": 1}
    )

    if not leaderboard:
        raise HTTPException(status_code=404, detail="Leaderboard not generated")

    passed = leaderboard.get("selected_resume_candidates", [])

    if candidate_id not in passed:
        raise HTTPException(
            status_code=403,
            detail="Candidate did not pass resume round"
        )
    


def verify_candidate_passed_coding(candidate_id, contest_id):

    leaderboard = contest_leaderboard.find_one(
        {"contest_id": ObjectId(contest_id)},
        {"selected_coding_candidates": 1}
    )

    if not leaderboard:
        raise HTTPException(status_code=404, detail="Leaderboard not generated")

    passed = leaderboard.get("selected_coding_candidates", [])

    if candidate_id not in passed:
        raise HTTPException(
            status_code=403,
            detail="Candidate did not pass coding round"
        )



def verify_candidate_passed_concept(candidate_id, contest_id):

    leaderboard = contest_leaderboard.find_one(
        {"contest_id": ObjectId(contest_id)},
        {"selected_concept_candidates": 1}
    )

    if not leaderboard:
        raise HTTPException(status_code=404, detail="Leaderboard not generated")

    passed = leaderboard.get("selected_concept_candidates", [])

    if candidate_id not in passed:
        raise HTTPException(
            status_code=403,
            detail="Candidate did not pass concept round"
        )




def verify_coding_question(contest, question_id):
    coding_ids = contest["coding_round"]["questions"]

    try:
        question_obj_id = ObjectId(question_id)
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail="Invalid coding question id"
        )

    if question_obj_id not in coding_ids:
        raise HTTPException(
            status_code=400,
            detail="Invalid coding question id"
        )

    return question_obj_id



def verify_concept_question(contest, question_id):

    concept_questions = contest["concept_round"]["questions"]

    if question_id not in concept_questions:
        raise HTTPException(
            status_code=400,
            detail="Invalid concept question id"
        )
    

def verify_hr_question(contest, question_id):

    hr_questions = contest["hr_round"]["questions"]

    if question_id not in hr_questions:
        raise HTTPException(
            status_code=400,
            detail="Invalid HR question id"
        )
    







def verify_coding_submit(contest_candidate):
    coding = contest_candidate.get("coding")

    if not coding:
        raise HTTPException(
            status_code=400,
            detail="Coding round not started"
        )
    
    if coding.get("submitted_at"):
        raise HTTPException(
                status_code=400,
                detail="Candidate already submitted"
            )
        
        


def verify_concept_submit(contest_candidate):
    concept = contest_candidate.get("concept")

    if not concept:
        raise HTTPException(
            status_code=400,
            detail="Concept round not started"
        )
    
    if concept.get("submitted_at"):
        raise HTTPException(
                status_code=400,
                detail="Candidate already submitted"
            )
        


def verify_hr_submit(contest_candidate):
    hr = contest_candidate.get("hr")

    if not hr:
        raise HTTPException(
            status_code=400,
            detail="HR round not started"
        )
    
    if hr.get("submitted_at"):
        raise HTTPException(
                status_code=400,
                detail="Candidate already submitted"
            )
        

    
