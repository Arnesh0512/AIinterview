import requests
import base64
from fastapi import HTTPException
from utils.reader import GITHUB_API_KEY
from database import github_question_collection
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Callable, Awaitable, Union
import asyncio
from fastapi.security import HTTPAuthorizationCredentials
import inspect
from utils.time import generate_timestamp

def get_headers():
    return {
        "Authorization": f"Bearer {GITHUB_API_KEY}",
        "Accept": "application/vnd.github+json"
    }



def fetch_repositories(github_url: str):
    username = github_url.strip().rstrip("/").split("/")[-1]

    url = f"https://api.github.com/users/{username}/repos"
    response = requests.get(url, headers=get_headers())
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="GitHub API error")

    repos = response.json()

    if not repos:
        raise HTTPException(status_code=404, detail="No repositories found")

    repo_list = []

    for index, repo in enumerate(repos, start=1):
        repo_list.append({
            "number": index,
            "name": repo["name"],
            "link": repo["html_url"]
        })

    return repo_list


def fetch_repo_details(selected_repo_link):

    parts = selected_repo_link.rstrip("/").split("/")
    owner = parts[-2]
    repo_name = parts[-1]

    repo_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    repo_response = requests.get(repo_url, headers=get_headers())


    repo_data = repo_response.json()
    repo_name = repo_data.get("name")
    repo_description = repo_data.get("description")
    languages_url = repo_data.get("languages_url")


    lang_response = requests.get(languages_url, headers=get_headers())
    languages = {}
    if lang_response.status_code == 200:
        languages = lang_response.json()


    readme_url = f"https://api.github.com/repos/{owner}/{repo_name}/readme"
    readme_response = requests.get(readme_url, headers=get_headers())
    readme_content = None
    if readme_response.status_code == 200:
        readme_content = readme_response.json().get("content", "")
        decoded_bytes = base64.b64decode(readme_content)
        decoded_readme = decoded_bytes.decode("utf-8")

    if not (repo_description.strip() or decoded_readme.strip()):
        raise HTTPException(
            status_code=400,
            detail="Repository contains insufficient analyzable content."
        )

    

    return {
        "repo_name": repo_name,
        "description": repo_description,
        "languages": languages,
        "readme": decoded_readme
    }





def previous_github_session_questions(
    github_id: ObjectId,
    x: int = None,
    session_number: int = None,
):
    
    session_dict = {}
    sessions_used = {}
    
    search_query = {
        "github_id": github_id,
        "status": "passive"
        }

    if session_number:
        search_query["session_number"] = session_number

    all_sessions = list(
        github_question_collection.find(
            search_query,
            {
                "_id": 1,
                "session_number": 1,
                "question_bank": 1,
                "timestamp": 1
            }
        ).sort("timestamp", -1)
    )


    if not session_number:
        latest_sessions = {}

        for session in all_sessions:
            sn = session["session_number"]

            if sn not in latest_sessions:
                latest_sessions[sn] = session
        
        all_sessions = latest_sessions.values()


    sorted_sessions = sorted(
        all_sessions,
        key=lambda s: s["timestamp"],
        reverse=True
    )

    if x:
        sorted_sessions = sorted_sessions[:x]

    if len(sorted_sessions) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Need at least 2 sessions for combined feedback."
        )

    for idx, s in enumerate(sorted_sessions):
        sn = s["session_number"]
        sid = str(s["_id"])
        ts = s["timestamp"]

        session_dict[f"session_{idx+1}"] = {
            q.get("question", ""): q.get("answer", "")
            for q in s.get("question_bank", [])
            if q.get("answer")
        }

        sessions_used[str(ts)] = {
            "session_number": sn,
            "session_id": sid
        }

    return session_dict, sessions_used






async def auto_submit(
    github_id: str,
    question_session_id: str,
    token: str,
    start_time : datetime,
    duration: int,
    fun: Union[
    Callable[[str, str, datetime, HTTPAuthorizationCredentials], None],
    Callable[[str, str, datetime, HTTPAuthorizationCredentials], Awaitable[None]]
    ]
):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )

    end_time = start_time + timedelta(seconds=duration) + timedelta(minutes=1)
    now = generate_timestamp()
    wait_seconds = (end_time - now).total_seconds()

    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    if inspect.iscoroutinefunction(fun):
        await fun(github_id, question_session_id, generate_timestamp(), credentials)
    else:
        fun(github_id, question_session_id, generate_timestamp(), credentials)
