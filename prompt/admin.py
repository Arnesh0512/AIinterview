import json
from typing import List
from fastapi import HTTPException
from model import call_chatgpt


def validate_role_skills(role: str, skills: List[str]) -> bool:

    prompt = """
    You are an expert technical recruiter.

    You will be given a <role> required for a position
    and a <list of skills>.

    Determine if these skills are appropriate for the role.

    Return strictly JSON:

    {"valid": true/false}
    """

    content = f"Role: {role}, Skills: {', '.join(skills)}"


    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "validation",
            "schema": {
                "type": "object",
                "properties": {
                    "valid": {
                        "type": "boolean"
                    }
                },
                "required": ["valid"]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.4, response_format)

    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)

        if not isinstance(response_json["valid"], bool):
            raise ValueError("valid must be boolean")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI"
        )

    if not response_json["valid"]:
        raise HTTPException(
            status_code=400,
            detail="Role and skills mismatch"
        )





def generate_resume_questions(company: str ,role: str, skills: List[str], question_count: int) -> List[str]:

    prompt = """
You are an expert technical recruiter designing automated resume screening for a company.

Generate resume screening questions that can be answered directly by analyzing
the candidate's resume text.

The goal is to later evaluate if the resume demonstrates the required skills
and experience for the role.

Each question should help verify:

- whether the candidate has experience with the listed skills
- whether they have worked on relevant projects
- whether their experience aligns with the role

IMPORTANT RULES:
- Questions must be answerable using only the resume text
- Avoid subjective questions like "tell me about..."
- Prefer verification questions like:
  - "Does the candidate mention experience with X?"
  - "What project demonstrates use of X?"
  - "How many years of experience does the candidate show in X?"

Return strictly JSON:

{
"questions": ["q1", "q2", "q3"]
}
"""

    content = f"""
Company: {company}
Role: {role}
Skills: {", ".join(skills)}
Number of questions: {question_count}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "resume_questions",
            "schema": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["questions"]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.7, response_format)

    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)

        questions = response_json["questions"]

        if not isinstance(questions, list):
            raise ValueError("questions must be list")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI for resume questions"
        )

    return questions


def generate_concept_questions(role: str, skills: List[str], question_count: int) -> List[str]:

    prompt = """
You are a senior technical interviewer.

Generate concept interview questions that test
deep understanding of core technical concepts.

Return strictly JSON:

{
"questions": ["q1","q2","q3"]
}
"""

    content = f"""
Role: {role}
Skills: {", ".join(skills)}
Number of questions: {question_count}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "concept_questions",
            "schema": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["questions"]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.7, response_format)

    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)

        questions = response_json["questions"]

        if not isinstance(questions, list):
            raise ValueError("questions must be list")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI for concept questions"
        )

    return questions



def generate_hr_questions(role: str, question_count: int) -> List[str]:

    prompt = """
You are an HR interviewer.

Generate HR interview questions that evaluate:
communication,
behavior,
teamwork,
and work ethics.

Return strictly JSON:

{
"questions": ["q1","q2","q3"]
}
"""

    content = f"""
Role: {role}
Number of questions: {question_count}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "hr_questions",
            "schema": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["questions"]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.7, response_format)

    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)

        questions = response_json["questions"]

        if not isinstance(questions, list):
            raise ValueError("questions must be list")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI for HR questions"
        )

    return questions




