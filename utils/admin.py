from database import leetcode
from fastapi import HTTPException
from typing import List
import random

def generate_coding_ids(company:str, coding_question_count: int) -> List:
    total_count = leetcode.count_documents({
        "companies": company
    })


    if total_count < coding_question_count:
        raise HTTPException(status_code=400, detail=f"Not enough coding questions, only {total_count} available.")


    easy_questions = list(leetcode.aggregate([
        {"$match": {"companies": company, "difficulty": "Easy"}},
        {"$sample": {"size": coding_question_count}}
    ]))

    medium_questions = list(leetcode.aggregate([
        {"$match": {"companies": company, "difficulty": "Medium"}},
        {"$sample": {"size": coding_question_count}}
    ]))

    hard_questions = list(leetcode.aggregate([
        {"$match": {"companies": company, "difficulty": "Hard"}},
        {"$sample": {"size": coding_question_count}}
    ]))

    coding_pool = easy_questions + medium_questions + hard_questions

    final_coding = random.sample(coding_pool, coding_question_count)

    coding_ids = [q["_id"] for q in final_coding]

    return coding_ids 
