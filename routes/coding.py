from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from database import leetcode_collections, coding_collection, user_collection
from openai import OpenAI
from pydantic import BaseModel
import os
import random
import json

router = APIRouter(prefix="/leetcode", tags=["Coding"])

client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ============================================================
# Request Model for Code Submission (JSON Body)
# ============================================================
class CodeSubmission(BaseModel):
    candidate_id: str
    question_id: int
    code_answer: str


# ============================================================
# 1️⃣ COMPANY BASED QUESTIONS
# ============================================================
@router.get("/company")
def get_company_questions(candidate_id: str, company: str, n: int):

    try:
        ObjectId(candidate_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid candidate_id")

    query = {
        "companies": {"$regex": company, "$options": "i"}
    }

    questions = list(leetcode_collections.find(query))

    if not questions:
        raise HTTPException(status_code=404, detail="No questions found")

    selected = random.sample(questions, min(n, len(questions)))

    formatted = [
        {
            "question_id": q["question_id"],
            "task_id": q.get("task_id"),
            "problem_description": q["problem_description"]
        }
        for q in selected
    ]

    return {"questions": formatted}


# ============================================================
# 2️⃣ TOPIC BASED QUESTIONS
# ============================================================
@router.get("/topic")
def get_topic_questions(candidate_id: str, topic: str, n: int):

    try:
        ObjectId(candidate_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid candidate_id")

    query = {
        "tags": {"$regex": topic, "$options": "i"}
    }

    questions = list(leetcode_collections.find(query))

    if not questions:
        raise HTTPException(status_code=404, detail="No questions found")

    selected = random.sample(questions, min(n, len(questions)))

    formatted = [
        {
            "question_id": q["question_id"],
            "task_id": q.get("task_id"),
            "problem_description": q["problem_description"]
        }
        for q in selected
    ]

    return {"questions": formatted}


# ============================================================
# 3️⃣ SUBMIT CODE (JSON BODY + coding_collection)
# ============================================================
@router.post("/submit")
def submit_code(data: CodeSubmission):

    # ---------- Validate Candidate ----------
    try:
        candidate_id = ObjectId(data.candidate_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid candidate_id")

    question_doc = leetcode_collections.find_one({"question_id": data.question_id})

    if not question_doc:
        raise HTTPException(status_code=404, detail="Question not found")

    # ---------- Build Prompt ----------
    prompt = f"""
    Problem:
    {question_doc["problem_description"]}

    Candidate Code:
    {data.code_answer}

    Evaluate this solution.

    Provide:
    - Correctness analysis
    - Time complexity
    - Space complexity
    - Improvements
    - Overall rating out of 10

    Return strictly VALID JSON:
    {{
        "correctness": "...",
        "time_complexity": "...",
        "space_complexity": "...",
        "improvements": "...",
        "rating": 0-10
    }}
    """

    # ---------- Call OpenAI (FORCED JSON MODE) ----------
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}  # 🔥 prevents JSON errors
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI evaluation failed: {str(e)}")

    content = response.choices[0].message.content

    if not content:
        raise HTTPException(status_code=500, detail="Empty AI response")

    try:
        feedback_json = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON returned by AI")

    # ---------- Store Attempt in coding_collection ----------
    coding_doc = {
        "Candidate_id": candidate_id,
        "question_id": data.question_id,
        "problem": question_doc["problem_description"],
        "answer": data.code_answer,
        "feedback": feedback_json,
        "created_at": datetime.now()
    }

    inserted = coding_collection.insert_one(coding_doc)

    # Append to user's coding attempts
    user_collection.update_one(
        {"_id": candidate_id},
        {
            "$push": {
                "coding": inserted.inserted_id
            }
        }
    )

    feedback_json["coding_document_id"] = str(inserted.inserted_id)

    return feedback_json