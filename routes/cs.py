from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from database import user_collection, question3_collection
from openai import OpenAI
from pydantic import BaseModel
import os
import json

router = APIRouter(prefix="/questionaire", tags=["Conceptual"])

client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ============================================================
# Request Models
# ============================================================

class GenerateQuestionsRequest(BaseModel):
    user_id: str
    topic: str
    num_questions: int


class SubmitAnswersRequest(BaseModel):
    user_id: str
    topic: str
    questions: list[str]
    answers: list[str]


# ============================================================
# ROUTE 1: Generate Conceptual Questions
# ============================================================

@router.post("/generate")
def generate_conceptual_questions(data: GenerateQuestionsRequest):

    # ---------------- Validate User ----------------
    try:
        user_id = ObjectId(data.user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = user_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ---------------- Build Prompt ----------------
    prompt = f"""
    Generate {data.num_questions} conceptual interview questions on the topic: {data.topic}.

    Questions must test deep understanding and reasoning.

    Return strictly VALID JSON in this format:
    {{
        "questions": ["q1", "q2", ...]
    }}
    """

    # ---------------- Call OpenAI ----------------
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI call failed: {str(e)}")

    content = response.choices[0].message.content

    if not content:
        raise HTTPException(status_code=500, detail="Empty AI response")

    try:
        questions_json = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON returned by AI")

    if "questions" not in questions_json:
        raise HTTPException(status_code=500, detail="AI response missing questions")

    # ---------------- Store in DB ----------------
    question_doc = {
        "Candidate_id": user_id,
        "topic": data.topic,
        "questions": questions_json["questions"],
        "created_at": datetime.now()
    }

    inserted = question3_collection.insert_one(question_doc)

    # Append reference to user
    user_collection.update_one(
        {"_id": user_id},
        {
            "$push": {
                "conceptual_attempts": inserted.inserted_id
            }
        }
    )

    questions_json["question_document_id"] = str(inserted.inserted_id)

    return questions_json


# ============================================================
# ROUTE 2: Submit Answers & Get Feedback
# ============================================================

@router.post("/submit")
def submit_conceptual_answers(data: SubmitAnswersRequest):

    # ---------------- Validate User ----------------
    try:
        user_id = ObjectId(data.user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = user_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ---------------- Validate QA ----------------
    if not data.questions or not data.answers:
        raise HTTPException(status_code=400, detail="Questions or answers missing")

    # ---------------- Build Prompt ----------------
    prompt = f"""
    Topic: {data.topic}

    Questions:
    {data.questions}

    Candidate Answers:
    {data.answers}

    Evaluate each answer carefully.

    Return strictly VALID JSON in this format:
    {{
        "feedback_per_question": [
            {{
                "question": "...",
                "feedback": "...",
                "score": 0-10
            }}
        ],
        "overall_feedback": "...",
        "score": 0-10
    }}
    """

    # ---------------- Call OpenAI ----------------
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI call failed: {str(e)}")

    content = response.choices[0].message.content

    if not content:
        raise HTTPException(status_code=500, detail="Empty AI response")

    try:
        feedback_json = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON returned by AI")

    # ---------------- Store Attempt ----------------
    attempt_doc = {
        "Candidate_id": user_id,
        "topic": data.topic,
        "questions": data.questions,
        "answers": data.answers,
        "feedback": feedback_json,
        "created_at": datetime.now()
    }

    inserted = question3_collection.insert_one(attempt_doc)

    user_collection.update_one(
        {"_id": user_id},
        {
            "$push": {
                "conceptual_attempts": inserted.inserted_id
            }
        }
    )

    feedback_json["attempt_id"] = str(inserted.inserted_id)

    return feedback_json