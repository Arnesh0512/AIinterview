import requests
import base64
from fastapi import HTTPException
from utils.reader import GITHUB_API_KEY



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







