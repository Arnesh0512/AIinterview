from utils.reader import GITHUB_API_KEY
from database import github_collection
from fastapi import HTTPException, status
from bson import ObjectId
from bson.errors import InvalidId
from typing import Tuple
from database import github_question_collection
from datetime import datetime, timezone
import requests

def get_headers():
    return {
        "Authorization": f"Bearer {GITHUB_API_KEY}",
        "Accept": "application/vnd.github+json"
    }


def verify_github_link(github_link: str):

    if not github_link:
        raise HTTPException(status_code=400, detail="GitHub link required")

    github_link = github_link.strip().rstrip("/")

    if "github.com" not in github_link:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")

    parts = github_link.split("/")

    if len(parts) < 4:
        raise HTTPException(status_code=400, detail="Invalid GitHub profile URL")

    username = parts[-1]

    url = f"https://api.github.com/users/{username}"
    response = requests.get(url, headers=get_headers())

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="GitHub user not found")




def verify_github_repo(repo_link: str):

    if not repo_link:
        raise HTTPException(status_code=400, detail="Repository link required")

    repo_link = repo_link.strip().rstrip("/")

    if "github.com" not in repo_link:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")

    parts = repo_link.split("/")

    if len(parts) < 5:
        raise HTTPException(status_code=400, detail="Invalid repository URL format")

    owner = parts[-2]
    repo_name = parts[-1]

    url = f"https://api.github.com/repos/{owner}/{repo_name}"
    response = requests.get(url, headers=get_headers())

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Repository not found")




def verify_github_link_repo(github_link: str, repo_link: str):

    verify_github_link(github_link)
    verify_github_repo(repo_link)
    username = github_link.strip().rstrip("/").split("/")[-1]
    repo_owner = repo_link.strip().rstrip("/").split("/")[-2]

    if username.lower() != repo_owner.lower():
        raise HTTPException(
            status_code=400,
            detail="Repository does not belong to provided GitHub profile"
        )



def verify_github(
        github_id: str, candidate_id: ObjectId
        ) -> Tuple[dict, ObjectId]:

    try:
        github_obj_id = ObjectId(github_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid github_id"
        )
    
    github_doc = github_collection.find_one({
        "_id": github_obj_id,
        "candidate_id": candidate_id
    })

    if not github_doc:
        raise HTTPException(
            status_code=404,
            detail="GitHub document not found"
        )

    return github_doc, github_obj_id




def verify_question_session(
    question_session_id: str,
    github_id: ObjectId
) -> Tuple[dict, ObjectId]:

    try:
        session_obj_id = ObjectId(question_session_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question_session_id"
        )

    session_doc = github_question_collection.find_one({
        "_id": session_obj_id,
        "github_id": github_id
    })

    if not session_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question session not found"
        )

    return session_doc, session_obj_id



def verify_question_number(
    session_doc: dict,
    question_number: int
):

    question_bank = session_doc.get("question_bank", [])

    if question_number < 1 or question_number > len(question_bank):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question_number"
        )


def verify_session_status(session_doc: dict):

    if session_doc.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active"
        )
    
def verify_session_status2(session_doc: dict):

    if session_doc.get("status") != "passive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not passive"
        )




def verify_session_time(session_doc: dict, session_obj_id: ObjectId):

    start_time = session_doc["timestamp"]
    total_time = session_doc["time"]

    now = datetime.now(timezone.utc)
    elapsed_minutes = (now - start_time).total_seconds() / 60

    if elapsed_minutes > total_time:

        github_question_collection.update_one(
            {"_id": session_obj_id},
            {"$set": {"status": "passive"}}
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session time expired"
        )









