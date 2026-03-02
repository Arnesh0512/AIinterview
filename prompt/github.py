import json
from fastapi import HTTPException
from model import call_chatgpt
from utils.github import fetch_repo_details





def process_repo(selected_repo_link):

    details = fetch_repo_details(selected_repo_link)



    prompt = f"""
        You are a professional GitHub repository analyzer.

        Analyze the repository based on:
        - Project description
        - Programming languages used
        - README content

        Provide:

        - Project Overview (less than 300 words)
        - Technical Stack & Tools
        - Architecture / Design Insights
        - Complexity & Developer Skill Level
        - Strengths
        - Weaknesses / Improvement Areas
        - Possible Interview Questions Focus Areas

        Be factual.
        Do NOT invent features not present.
        Return only one complete string summary.
    """

    content = f"""
        Repository Name: {details.get("repo_name")}

        Description:
        {details.get("description")}

        Languages Used:
        {details.get("languages")}

        README:
        {details.get("readme")}
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "repo_summary",
            "schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string"
                    }
                },
                "required": ["summary"]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.2, response_format)

    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)
        summary_str = response_json["summary"]
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI"
        )

    return {
        "repo_name": details.get("repo_name"),
        "summary": summary_str
    }




def generate_github_question(repo_summary: str, num_questions: int):

    prompt = f"""
    You are a senior technical interviewer.

    Based on the repository summary below, generate {num_questions} 
    deep technical interview questions.

    Questions should test:
    - Architecture understanding
    - Code design decisions
    - Technology choices
    - Scalability
    - Optimization
    - Edge cases
    - Security considerations

    Questions must:
    - Be specific to this project
    - Not generic
    - Encourage deep explanation
    - Be open-ended

    Return strictly in JSON format:

    {{
        "questions": ["question1", "question2", ...]
    }}
    #Dont ask multiple questions in any single question. Each question should be standalone and focused on one aspect.
    """

    content = f"""
    Repository Summary:
    {repo_summary}
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "github_questions",
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

    response = call_chatgpt(prompt, content, 0.4, response_format)

    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)
        if not isinstance(response_json["questions"], list):
            raise ValueError("Questions must be a list")
        
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI"
        )

    return response_json




def evaluate_github_answers(repo_summary: str, question_bank: list):

    prompt = """
    You are a senior software architect and technical interviewer.

    You are evaluating answers related to a GitHub repository project.

    Evaluate each answer based on:

    - Understanding of project architecture
    - Correctness of technical explanation
    - Depth of implementation knowledge
    - Design reasoning
    - Technology choices justification
    - Awareness of scalability, security, and edge cases

    Scoring Rules:
    - Score each answer from 0 to 10
    - Be strict and realistic
    - Penalize vague or generic answers
    - Reward deep architectural understanding
    - Provide actionable feedback

    Also provide:
    - Overall feedback
    - Overall score (0–10)

    Return strictly valid JSON in this format:

    {
        "feedback_per_question": [
            {
                "question_number": 1,
                "feedback": "...",
                "score": 8
            }
        ],
        "overall_feedback": "...",
        "overall_score": 7.5
    }
    """

    content = f"""
    Repository Summary:
    {repo_summary}

    Question & Answers:
    {json.dumps(question_bank, indent=2)}
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "github_evaluation_output",
            "schema": {
                "type": "object",
                "properties": {
                    "feedback_per_question": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_number": {"type": "integer"},
                                "feedback": {"type": "string"},
                                "score": {"type": "number"}
                            },
                            "required": [
                                "question_number",
                                "feedback",
                                "score"
                            ]
                        }
                    },
                    "overall_feedback": {"type": "string"},
                    "overall_score": {"type": "number"}
                },
                "required": [
                    "feedback_per_question",
                    "overall_feedback",
                    "overall_score"
                ]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.2, response_format)

    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)

        # Basic validation
        if not isinstance(response_json["feedback_per_question"], list):
            raise ValueError("feedback_per_question must be list")


    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI"
        )

    return response_json




















