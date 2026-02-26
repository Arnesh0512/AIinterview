import os
import requests
from datetime import datetime
from bson import ObjectId
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from openai import OpenAI
from database import user_collection, github_collection

load_dotenv()

# Initialize OpenAI
client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

candidates_collection = user_collection


def scrape_all_projects(candidate_id):
    if isinstance(candidate_id, str):
        candidate_id = ObjectId(candidate_id)

    candidate = candidates_collection.find_one({"_id": candidate_id})

    if not candidate or "github" not in candidate:
        raise ValueError("GitHub link not found for candidate.")

    github_url = candidate["github"].rstrip("/") + "?tab=repositories"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(github_url, headers=headers)

    if response.status_code != 200:
        raise Exception("Failed to fetch GitHub profile.")

    soup = BeautifulSoup(response.text, "html.parser")

    # ✅ NEW SELECTOR
    repos = soup.find_all("a", attrs={"itemprop": "name codeRepository"})

    # Fallback selector (new GitHub layout)
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


def scrape_and_summarize_project(candidate_id, project_number):
    if isinstance(candidate_id, str):
        candidate_id = ObjectId(candidate_id)

    project_number = str(project_number)

    candidate = candidates_collection.find_one({"_id": candidate_id})

    if "github" not in candidate or project_number not in candidate["github"]:
        raise ValueError("Project not found.")

    project = candidate["github"][project_number]
    repo_url = project["url"]

    response = requests.get(repo_url)
    if response.status_code != 200:
        raise Exception("Failed to fetch repository page.")

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract repo description
    description_tag = soup.find("p", {"class": "f4 my-3"})
    description = description_tag.text.strip() if description_tag else ""

    # Extract README
    readme_div = soup.find("article", {"class": "markdown-body"})
    readme_text = readme_div.get_text(separator="\n") if readme_div else ""

    full_text = f"""
    Project Name: {project['name']}

    Description:
    {description}

    README:
    {readme_text}
    """

    if not full_text.strip():
        raise ValueError("No content found to summarize.")

    # Send to ChatGPT
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

    response_ai = client_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a senior technical recruiter analyzing GitHub projects."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    summary_text = response_ai.choices[0].message.content

    # Store in github_collection
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

    # Append summary reference in candidate.github_sum
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