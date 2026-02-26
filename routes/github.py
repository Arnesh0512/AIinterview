from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from database import user_collection, github_collection
from github import scrape_all_projects, scrape_and_summarize_project
from openai import OpenAI
import os
import json

router = APIRouter(prefix="/github", tags=["GitHub"])

client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

question_collection = github_collection.database["github_questions"]


@router.post("/update")
def update_repos(user_id: str):

    try:
        user_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    projects = scrape_all_projects(user_id)

    return {"message": "Repositories updated", "new_projects": projects}



@router.get("/repos")
def get_repos(user_id: str):

    try:
        user_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = user_collection.find_one({"_id": user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"repos": user.get("github", {})}

@router.post("/questions")
def generate_repo_questions(user_id: str, repo_number: str, num_questions: int):

    try:
        user_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = user_collection.find_one({"_id": user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "github_repos" not in user or repo_number not in user["github_repos"]:
        raise HTTPException(status_code=400, detail="Repository not found")

    # Generate summary if missing
    if repo_number not in user.get("github_sum", {}):
        scrape_and_summarize_project(user_id, repo_number)

    # Refresh user document
    user = user_collection.find_one({"_id": user_id})

    summary_id = user["github_sum"][repo_number]["summary_id"]
    summary_doc = github_collection.find_one({"_id": summary_id})

    if not summary_doc:
        raise HTTPException(status_code=404, detail="Summary not found")

    prompt = f"""
    Based on this GitHub project summary, generate {num_questions} interview questions.

    Return strictly JSON in this format:
    {{
        "questions": ["q1", "q2", ...]
    }}

    Summary:
    {summary_doc["summary"]}
    """

    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"}  # 🔥 THIS FIXES THE ERROR
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI call failed: {str(e)}")

    content = response.choices[0].message.content

    if not content:
        raise HTTPException(status_code=500, detail="Empty AI response")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON returned by AI")


@router.post("/submit-answers")
def submit_repo_answers(user_id: str, repo_number: str, qa_data: dict):

    # ---------------- Validate user_id ----------------
    try:
        user_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = user_collection.find_one({"_id": user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "github_sum" not in user or repo_number not in user["github_sum"]:
        raise HTTPException(status_code=400, detail="Repository summary not found")

    summary_id = user["github_sum"][repo_number]["summary_id"]
    summary_doc = github_collection.find_one({"_id": summary_id})

    if not summary_doc:
        raise HTTPException(status_code=404, detail="Summary document not found")

    # ---------------- Validate QA Data ----------------
    if not qa_data.get("questions") or not qa_data.get("answers"):
        raise HTTPException(status_code=400, detail="Questions or answers missing")

    # ---------------- Build Prompt ----------------
    prompt = f"""
    Project Summary:
    {summary_doc["summary"]}

    Questions:
    {qa_data["questions"]}

    Answers:
    {qa_data["answers"]}

    Evaluate each answer carefully.

    Return strictly VALID JSON in this format:
    {{
        "feedback_per_question": [
            {{
                "question": "...",
                "feedback": "..."
            }}
        ],
        "overall_feedback": "..."
    }}
    """

    # ---------------- Call OpenAI (FORCED JSON MODE) ----------------
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}  # 🔥 Critical Fix
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
    question_doc = {
        "Candidate_id": user_id,
        "repo_number": repo_number,
        "summary_id": summary_id,
        "questions": qa_data["questions"],
        "answers": qa_data["answers"],
        "feedback": feedback_json,
        "created_at": datetime.now()
    }

    inserted = question_collection.insert_one(question_doc)

    # Append attempt ID safely
    user_collection.update_one(
        {"_id": user_id},
        {
            "$push": {
                f"github_sum.{repo_number}.question_id": inserted.inserted_id
            }
        }
    )

    feedback_json["question_document_id"] = str(inserted.inserted_id)

    return feedback_json

@router.get("/history")
def get_repo_history(user_id: str, repo_number: str):

    try:
        user_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    attempts = list(question_collection.find({
        "Candidate_id": user_id,
        "repo_number": repo_number
    }))

    formatted = []

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

        formatted.append({
            "attempt_id": str(attempt["_id"]),
            "qa": qa_list,
            "overall_feedback": feedback_data.get("overall_feedback"),
            "timestamp": attempt.get("created_at")
        })

    return {"history": formatted}