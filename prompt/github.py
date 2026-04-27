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


def generate_github_question(
    repo_summary: str,
    num_questions: int,
    previous_sessions: list
):

    prompt = f"""
You are a senior technical interviewer conducting a multi-round adaptive interview.

You will receive:
1) Repository Summary
2) Previous Interview Sessions

Previous Sessions are provided as a dictionary in the following format:

{{
    "session_1": {{
        "Question text 1": "Answer text 1",
        "Question text 2": "Answer text 2"
    }},
    "session_2": {{
        ...
    }}
}}

INTERPRETATION RULES:

- If Previous Sessions is an empty dictionary ({{}}):
  → This means this is the FIRST interview round.
  → Generate foundational to intermediate level questions.
  → Cover major architectural and technical components.
  → Ensure broad coverage of the project.

- If Previous Sessions contains data:
  → session_1 is the most recent session.
  → Higher session numbers represent older sessions.
  → Each key inside a session is a question and its value is the candidate’s answer.
  → You must:
      - Avoid repeating previous questions
      - Identify weak or shallow answers
      - Identify strong architectural understanding
      - Identify untouched components of the repository
      - Increase overall difficulty progressively
      - Focus more on:
            * Weak architectural explanations
            * Scalability gaps
            * Edge cases not discussed
            * Security considerations not explored
            * Deep system-level reasoning

Question Generation Rules:
- Generate exactly {num_questions} questions.
- Each list item must contain ONLY ONE question.
- Do NOT combine multiple questions into one.
- Include a mix of:
      * Architecture understanding
      * Design decisions
      * Scalability
      * Optimization
      * Edge cases
      * Security considerations
- Ensure increasing difficulty order within this round.
- Questions must be highly specific to the repository.
- Do NOT mention previous sessions explicitly in the question text.
- Do NOT provide answers.
- Do NOT add explanations.

Return strictly valid JSON in this format:
{{"questions": ["q1", "q2", ..., "qn"]}}
"""

    content = f"""
Repository Summary:
{repo_summary}

Previous Sessions:
{json.dumps(previous_sessions, indent=2)}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "github_question_output",
            "schema": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
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

        if not isinstance(response_json.get("questions"), list):
            raise ValueError("Questions must be a list")

        if len(response_json["questions"]) != num_questions:
            raise ValueError("Incorrect number of questions returned")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI"
        )

    return response_json



def evaluate_github_answers(repo_summary: str, question_bank: list):

    prompt = """
    You are a senior software architect and technical interviewer.

    You are evaluating answers related to a GitHub repository project based on his provided repository summary.

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


def generate_github_combined_diff_session_feedback(repo_summary: str, session_data: dict):

    prompt = """
You are a senior technical interview evaluator.

You will receive:
1) Repository Summary
2) Multiple completed interview sessions.

Sessions are provided as a dictionary in this format:

{
    "session_1": {
        "Question text 1": "Answer text 1",
        "Question text 2": "Answer text 2"
    },
    "session_2": {
        ...
    }
}

Interpretation Rules:

- session_1 is the most recent session.
- Higher session numbers represent older sessions.
- Each key inside a session is a question and its value is the candidate's answer.

Instructions:
- Evaluate overall technical progression.
- Identify architectural understanding growth.
- Identify improvement patterns.
- Identify repeated weaknesses.
- Identify consistent strengths.
- Evaluate depth growth across sessions.
- Evaluate system design maturity progression.
- Compare recent sessions with older ones.
- Be strict, analytical, and professional.
- Provide structured feedback (strengths, weaknesses, progression, recommendations).
- Do NOT mention JSON or formatting.

Return strictly valid JSON:
{
  "feedback": {
    "improvement": "detailed improvement analysis",
    "weaknesses": "persistent or current weaknesses",
    "strengths": "consistent or emerging strengths",
    "recommendations": "specific next-step recommendations"
  }
}
"""

    content = f"""
Repository Summary:
{repo_summary}

Session wise Question & Answers:
{json.dumps(session_data, indent=2)}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "github_combined_feedback_output",
            "schema": {
                "type": "object",
                "properties": {
                    "feedback": {
                        "type": "object",
                        "properties": {
                            "improvement": {"type": "string"},
                            "weaknesses": {"type": "string"},
                            "strengths": {"type": "string"},
                            "recommendations": {"type": "string"}
                        },
                        "required": ["improvement", "weaknesses", "strengths", "recommendations"],
                        "additionalProperties": False
                    }
                },
                "required": ["feedback"],
                "additionalProperties": False
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.2, response_format)

    try:
        content = response.choices[0].message.content
        result = json.loads(content)
        return result["feedback"]
    except:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI"
        )



def generate_github_combined_same_session_feedback(repo_summary: str, session_data: dict):

    prompt = """
You are a senior technical interview evaluator.

You will receive:
1) Repository Summary
2) Multiple reattempts of the SAME interview session.

Sessions are provided as a dictionary in this format:

{
    "session_1": {
        "Question text 1": "Answer text 1",
        "Question text 2": "Answer text 2"
    },
    "session_2": {
        ...
    }
}

Interpretation Rules:

- session_1 is the most recent attempt.
- Higher session numbers represent older attempts.
- Each key inside a session is a question and its value is the candidate's answer.
- All sessions correspond to the same interview round repeated over time.

Instructions:
- Evaluate progression across attempts.
- Identify architectural depth improvement.
- Identify areas of improvement.
- Identify areas where mistakes persist.
- Evaluate correction of past weaknesses.
- Evaluate depth growth and system design maturity progression.
- Compare latest attempt with older attempts.
- Be strict, analytical, and professional.
- Provide structured feedback (improvement, weaknesses, strengths, recommendations).
- Do NOT mention JSON or formatting.

Return strictly valid JSON:
{
  "feedback": {
    "improvement": "detailed improvement analysis",
    "weaknesses": "persistent or current weaknesses",
    "strengths": "consistent or emerging strengths",
    "recommendations": "specific next-step recommendations"
  }
}
"""

    content = f"""
Repository Summary:
{repo_summary}

Session wise Question & Answers:
{json.dumps(session_data, indent=2)}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "github_combined_feedback_output",
            "schema": {
                "type": "object",
                "properties": {
                    "feedback": {
                        "type": "object",
                        "properties": {
                            "improvement": {"type": "string"},
                            "weaknesses": {"type": "string"},
                            "strengths": {"type": "string"},
                            "recommendations": {"type": "string"}
                        },
                        "required": ["improvement", "weaknesses", "strengths", "recommendations"],
                        "additionalProperties": False
                    }
                },
                "required": ["feedback"],
                "additionalProperties": False
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.2, response_format)

    try:
        content = response.choices[0].message.content
        result = json.loads(content)
        return result["feedback"]
    except:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI"
        )















