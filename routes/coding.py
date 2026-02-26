from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from database import leetcode_collections, question_collection, user_collection
from openai import OpenAI
import os
import random
import json

router = APIRouter(prefix="/leetcode", tags=["Coding"])

client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@router.get("/company")
def get_company_questions(candidate_id: str, company: str, difficulty: str, n: int):

    try:
        candidate_id = ObjectId(candidate_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid candidate_id")

    query = {
        "companies": {"$regex": company.lower()},
        "difficulty": difficulty
    }

    questions = list(leetcode_collections.find(query))

    if not questions:
        raise HTTPException(status_code=404, detail="No questions found")

    selected = random.sample(questions, min(n, len(questions)))

    formatted = []

    for q in selected:
        formatted.append({
            "question_id": q["question_id"],
            "task_id": q["task_id"],
            "problem_description": q["problem_description"]
        })

    return {"questions": formatted}


@router.get("/topic")
def get_topic_questions(candidate_id: str, topic: str, difficulty: str, n: int):

    try:
        candidate_id = ObjectId(candidate_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid candidate_id")

    query = {
        "tags": {"$regex": topic, "$options": "i"},
        "difficulty": difficulty
    }

    questions = list(leetcode_collections.find(query))

    if not questions:
        raise HTTPException(status_code=404, detail="No questions found")

    selected = random.sample(questions, min(n, len(questions)))

    formatted = []

    for q in selected:
        formatted.append({
            "question_id": q["question_id"],
            "task_id": q["task_id"],
            "problem_description": q["problem_description"]
        })

    return {"questions": formatted}



@router.post("/submit")
def submit_code(candidate_id: str, question_id: int, code_answer: str):

    try:
        candidate_id = ObjectId(candidate_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid candidate_id")

    question_doc = leetcode_collections.find_one({"question_id": question_id})

    if not question_doc:
        raise HTTPException(status_code=404, detail="Question not found")

    prompt = f"""
    Problem:
    {question_doc["problem_description"]}

    Candidate Code:
    {code_answer}

    Evaluate this solution.

    Provide:
    - Correctness analysis
    - Time complexity
    - Space complexity
    - Improvements
    - Overall rating out of 10

    Return strictly JSON:
    {{
        "correctness": "...",
        "time_complexity": "...",
        "space_complexity": "...",
        "improvements": "...",
        "rating": 0-10
    }}
    """

    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    feedback_json = json.loads(response.choices[0].message.content)

    # Store attempt
    coding_doc = {
        "Candidate_id": candidate_id,
        "question_id": question_id,
        "problem": question_doc["problem_description"],
        "answer": code_answer,
        "feedback": feedback_json,
        "created_at": datetime.now()
    }

    inserted = question_collection.insert_one(coding_doc)

    # Append to user's coding list
    user_collection.update_one(
        {"_id": candidate_id},
        {
            "$push": {
                "coding": inserted.inserted_id
            }
        }
    )

    feedback_json["question_document_id"] = str(inserted.inserted_id)

    return feedback_json


