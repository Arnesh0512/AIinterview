import os
import requests
import base64
import json
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from openai import OpenAI
from database import user_collection, github_collection

# ---------------- Initialize ----------------
client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
candidates_collection = user_collection


# ============================================================
# 1️⃣ SCRAPE ALL REPOSITORIES (HTML fallback method)
# ============================================================
def scrape_all_projects(candidate_id):

    if isinstance(candidate_id, str):
        candidate_id = ObjectId(candidate_id)

    candidate = candidates_collection.find_one({"_id": candidate_id})

    if not candidate or "github" not in candidate:
        raise HTTPException(status_code=400, detail="GitHub link not found.")

    github_url = candidate["github"].rstrip("/") + "?tab=repositories"

    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(github_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch GitHub profile.")

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")

    repos = soup.find_all("a", attrs={"itemprop": "name codeRepository"})

    if not repos:
        repos = soup.find_all("a", attrs={"data-testid": "repository-item-link"})

    existing_projects = candidate.get("github_repos", {})
    next_index = len(existing_projects) + 1
    new_projects = {}

    for repo in repos:
        repo_name = repo.text.strip()
        repo_link = "https://github.com" + repo["href"]

        if repo_link not in [v["url"] for v in existing_projects.values()]:
            new_projects[str(next_index)] = {
                "name": repo_name,
                "url": repo_link
            }
            next_index += 1

    if new_projects:
        candidates_collection.update_one(
            {"_id": candidate_id},
            {"$set": {f"github_repos.{k}": v for k, v in new_projects.items()}}
        )

    return new_projects


# ============================================================
# 2️⃣ SCRAPE & SUMMARIZE SINGLE PROJECT (GitHub API Based)
# ============================================================
def scrape_and_summarize_project(candidate_id, project_number):

    if isinstance(candidate_id, str):
        candidate_id = ObjectId(candidate_id)

    project_number = str(project_number)

    candidate = candidates_collection.find_one({"_id": candidate_id})

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if "github_repos" not in candidate or project_number not in candidate["github_repos"]:
        raise HTTPException(status_code=400, detail="Project not found")

    project = candidate["github_repos"][project_number]
    repo_url = project["url"].rstrip("/")

    # Extract username and repo name
    try:
        parts = repo_url.split("github.com/")[1]
        username, repo_name = parts.split("/")[:2]
    except:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Mozilla/5.0"
    }

    # ---------- Fetch Repo Metadata ----------
    repo_api = f"https://api.github.com/repos/{username}/{repo_name}"
    repo_response = requests.get(repo_api, headers=headers)

    if repo_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch repository info")

    repo_data = repo_response.json()

    description = repo_data.get("description", "")
    language = repo_data.get("language", "")
    stars = repo_data.get("stargazers_count", 0)
    forks = repo_data.get("forks_count", 0)

    # ---------- Fetch README ----------
    readme_text = ""
    readme_api = f"https://api.github.com/repos/{username}/{repo_name}/readme"
    readme_response = requests.get(readme_api, headers=headers)

    if readme_response.status_code == 200:
        readme_json = readme_response.json()
        content_encoded = readme_json.get("content", "")
        if content_encoded:
            readme_text = base64.b64decode(content_encoded).decode("utf-8", errors="ignore")

    full_text = f"""
    Project Name: {project['name']}

    Description:
    {description}

    Primary Language:
    {language}

    Stars: {stars}
    Forks: {forks}

    README:
    {readme_text}
    """

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="No content found to summarize")

    # ---------- Summarize with OpenAI ----------
    prompt = f"""
    Summarize this GitHub project in less than 600 words.
    Include:
    - Purpose
    - Tech stack
    - Features
    - Complexity
    - Skills demonstrated

    Project Content:
    {full_text}
    """

    try:
        response_ai = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a senior technical recruiter analyzing GitHub projects."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI summarization failed: {str(e)}")

    summary_text = response_ai.choices[0].message.content

    summary_doc = {
        "Candidate_id": candidate_id,
        "project_number": project_number,
        "project_name": project["name"],
        "project_url": repo_url,
        "summary": summary_text,
        "created_at": datetime.now()
    }

    inserted = github_collection.insert_one(summary_doc)
    summary_id = inserted.inserted_id

    candidates_collection.update_one(
        {"_id": candidate_id},
        {
            "$set": {
                f"github_sum.{project_number}": {
                    "summary_id": summary_id,
                    "timestamp": datetime.now()
                }
            }
        }
    )

    return {
        "summary_id": str(summary_id),
        "summary": summary_text
    }


# ============================================================
# 3️⃣ GENERATE QUESTIONS (FIXED JSON ERROR)
# ============================================================
def generate_questions_from_summary(summary_text, num_questions):

    prompt = f"""
    Based on this GitHub project summary, generate {num_questions} interview questions.

    Return strictly JSON in this format:
    {{
        "questions": ["q1", "q2", ...]
    }}

    Summary:
    {summary_text}
    """

    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"}  # 🔥 prevents JSONDecodeError
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI question generation failed: {str(e)}")

    content = response.choices[0].message.content

    if not content:
        raise HTTPException(status_code=500, detail="Empty AI response")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON returned by AI")