from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from tempfile import NamedTemporaryFile
from datetime import datetime
from bson import ObjectId
import shutil
import os

from database import summary_collection, user_collection, question_collection
from pdf import process_resume
from verify.token import verify_access_token
from verify.user import verify_user_payload
from openai import OpenAI
import os

security = HTTPBearer()
router = APIRouter(prefix="/resume", tags=["Resume"])

client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

question_collection = summary_collection.database["questions"]

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    ocr_mode: str = "N",
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    user, candidate_id, email = verify_user_payload(payload)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF allowed")

    # Save temporarily
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
def get_all_resumes(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    user, candidate_id, email = verify_user_payload(payload)

    resumes = list(summary_collection.find(
        {"Candidate_id": candidate_id},
        {"Summary": 0}  # don't send full summary
    ))

    for r in resumes:
        r["_id"] = str(r["_id"])
        r["File_id"] = str(r["File_id"])

    return {"resumes": resumes}


@router.post("/questions")
def generate_questions(
    summary_id: str,
    num_questions: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    user, candidate_id, email = verify_user_payload(payload)

    summary_doc = summary_collection.find_one({
        "_id": ObjectId(summary_id),
        "Candidate_id": candidate_id
    })

    if not summary_doc:
        raise HTTPException(status_code=404, detail="Summary not found")

    prompt = f"""
    Based on the following resume summary, generate {num_questions} interview questions.
    Return response strictly in JSON format:
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

    import json
    questions_json = json.loads(response.choices[0].message.content)

    return questions_json


@router.post("/submit-answers")
def submit_answers(
    summary_id: str,
    qa_data: dict,   # {"questions":[...], "answers":[...]}
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    user, candidate_id, email = verify_user_payload(payload)

    summary_doc = summary_collection.find_one({
        "_id": ObjectId(summary_id),
        "Candidate_id": candidate_id
    })

    if not summary_doc:
        raise HTTPException(status_code=404, detail="Summary not found")

    prompt = f"""
    Resume Summary:
    {summary_doc["Summary"]}

    Questions:
    {qa_data["questions"]}

    Answers:
    {qa_data["answers"]}

    Evaluate each answer.
    Provide:
    - feedback per question
    - overall feedback

    Return JSON format:
    {{
        "feedback_per_question": [...],
        "overall_feedback": "..."
    }}
    """

    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    import json
    feedback_json = json.loads(response.choices[0].message.content)

    question_doc = {
        "Candidate_id": candidate_id,
        "summary_id": ObjectId(summary_id),
        "questions": qa_data["questions"],
        "answers": qa_data["answers"],
        "feedback": feedback_json,
        "created_at": datetime.now()
    }

    inserted = question_collection.insert_one(question_doc)


    user_collection.update_one(
    {
        "_id": candidate_id,
        "Resume.summary_id":ObjectId(summary_id)
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
def get_attempts(
    summary_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    payload = verify_access_token(token)
    user, candidate_id, email = verify_user_payload(payload)

    attempts = list(question_collection.find({
        "Candidate_id": candidate_id,
        "summary_id": ObjectId(summary_id)
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