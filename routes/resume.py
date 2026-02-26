from fastapi import APIRouter, UploadFile, File, HTTPException
from tempfile import NamedTemporaryFile
from datetime import datetime
from bson import ObjectId
import shutil
import os
import json
import certifi 
from database import summary_collection, user_collection, question_collection
from pdf import process_resume
from openai import OpenAI

router = APIRouter(prefix="/resume", tags=["Resume"])

client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@router.post("/upload")
async def upload_resume(
    candidate_id: str,
    file: UploadFile = File(...),
    ocr_mode: str = "N"
):
    try:
        candidate_id = ObjectId(candidate_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid candidate_id")

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF allowed")

    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        result = process_resume(temp_path, candidate_id, ocr_mode)
    finally:
        os.remove(temp_path)

    return {
        "message": "upload done",
        "summary_id": result["summary_id"]
    }


@router.get("/all")
def get_all_resumes(candidate_id: str):
    try:
        candidate_id = ObjectId(candidate_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid candidate_id")

    resumes = list(summary_collection.find(
        {"Candidate_id": candidate_id},
        {"Summary": 0}
    ))

    for r in resumes:
        r["_id"] = str(r["_id"])
        r["File_id"] = str(r["File_id"])

    return {"resumes": resumes}


@router.post("/questions")
def generate_questions(
    candidate_id: str,
    summary_id: str,
    num_questions: int
):
    try:
        candidate_id = ObjectId(candidate_id)
        summary_id = ObjectId(summary_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

    summary_doc = summary_collection.find_one({
        "_id": summary_id,
        "Candidate_id": candidate_id
    })

    if not summary_doc:
        raise HTTPException(status_code=404, detail="Summary not found")

    prompt = f"""
    Based on the following resume summary, generate {num_questions} interview questions.
    Return strictly JSON:
    {{
        "questions": ["q1", "q2", ...]
    }}

    Resume Summary:
    {summary_doc["Summary"]}
    """

    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    questions_json = json.loads(response.choices[0].message.content)

    return questions_json



@router.post("/submit-answers")
def submit_answers(
    candidate_id: str,
    summary_id: str,
    qa_data: dict
):
    # ------------------ Validate IDs ------------------
    try:
        candidate_id = ObjectId(candidate_id)
        summary_id = ObjectId(summary_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

    # ------------------ Fetch Summary ------------------
    summary_doc = summary_collection.find_one({
        "_id": summary_id,
        "Candidate_id": candidate_id
    })

    if not summary_doc:
        raise HTTPException(status_code=404, detail="Summary not found")

    # ------------------ Validate QA Data ------------------
    if not qa_data.get("questions") or not qa_data.get("answers"):
        raise HTTPException(status_code=400, detail="Questions or answers missing")

    # ------------------ Build Prompt ------------------
    prompt = f"""
    Resume Summary:
    {summary_doc["Summary"]}

    Questions:
    {qa_data["questions"]}

    Answers:
    {qa_data["answers"]}

    Evaluate each answer and return STRICTLY VALID JSON in this format:

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

    # ------------------ Call OpenAI (JSON Mode) ------------------
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}   # 🔥 Critical line
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI call failed: {str(e)}")

    # ------------------ Parse AI Response Safely ------------------
    content = response.choices[0].message.content

    if not content:
        raise HTTPException(status_code=500, detail="Empty AI response")

    try:
        feedback_json = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON returned by AI: {content}"
        )

    # ------------------ Store in DB ------------------
    question_doc = {
        "Candidate_id": candidate_id,
        "summary_id": summary_id,
        "questions": qa_data["questions"],
        "answers": qa_data["answers"],
        "feedback": feedback_json,
        "created_at": datetime.now()
    }

    inserted = question_collection.insert_one(question_doc)

    # Append attempt ID into user Resume list
    user_collection.update_one(
        {
            "_id": candidate_id,
            "Resume.summary_id": summary_id
        },
        {
            "$push": {
                "Resume.$.question_attempt_id": inserted.inserted_id
            }
        }
    )

    feedback_json["attempt_id"] = str(inserted.inserted_id)

    return feedback_json


@router.get("/attempts/{summary_id}")
def get_attempts(candidate_id: str, summary_id: str):

    try:
        candidate_id = ObjectId(candidate_id)
        summary_id = ObjectId(summary_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

    attempts = list(question_collection.find({
        "Candidate_id": candidate_id,
        "summary_id": summary_id
    }))

    formatted_attempts = []

    for attempt in attempts:

        questions = attempt.get("questions", [])
        answers = attempt.get("answers", [])
        feedback_data = attempt.get("feedback", {})
        feedback_per_question = feedback_data.get("feedback_per_question", [])

        qa_list = []

        for i in range(len(questions)):
            qa_list.append({
                "question": questions[i],
                "answer": answers[i] if i < len(answers) else None,
                "feedback": feedback_per_question[i] if i < len(feedback_per_question) else None
            })

        formatted_attempts.append({
            "attempt_id": str(attempt["_id"]),
            "qa": qa_list,
            "overall_feedback": feedback_data.get("overall_feedback"),
            "timestamp": attempt.get("created_at")
        })

    return {"attempts": formatted_attempts}