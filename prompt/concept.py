import json
from typing import List
from fastapi import HTTPException
from model import call_chatgpt


def generate_cs_topic_questions(topics: List[str], num_questions: int):

    prompt = f"""
    You are a senior computer science technical interviewer.

    Based on the given CS topics, generate {num_questions} 
    deep technical interview questions.

    Questions should test:
    - Core conceptual understanding
    - Internal working
    - Design decisions
    - Trade-offs
    - Complexity analysis
    - Edge cases
    - Real-world application

    Rules:
    - Questions must strictly relate to the provided topics
    - Do NOT generate generic questions
    - Each question must be standalone
    - Do NOT combine multiple questions into one
    - Encourage deep explanation
    - Return strictly valid JSON

    Output format:

    {{
        "questions": ["question1", "question2", ...]
    }}
    """

    content = f"""
    CS Topics:
    {", ".join(topics)}
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "cs_questions",
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



def evaluate_cs_topic_answers(
    topics: List[str],
    question_bank: List[dict]
):

    prompt = """
    You are a senior computer science technical interviewer.

    You are evaluating answers related to specific Computer Science topics.

    Evaluate each answer strictly based on:

    - Understanding of topic fundamentals
    - Correctness of technical explanation
    - Depth of implementation knowledge
    - Design reasoning
    - Trade-offs awareness
    - Scalability, security, and edge cases

    Scoring Rules:
    - Score each answer from 0 to 10
    - Be strict and realistic
    - Penalize vague or generic answers
    - Reward deep architectural and conceptual understanding
    - Provide actionable feedback

    Also provide:
    - Overall feedback
    - Overall score (0–10)

    IMPORTANT:
    - Do not hallucinate missing answers
    - Evaluate only based on given response
    - Return strictly valid JSON

    Format:

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
    Topics Covered:
    {", ".join(topics)}

    Question & Answers:
    {json.dumps(question_bank, indent=2)}
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "cs_evaluation_output",
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

        if not isinstance(response_json["feedback_per_question"], list):
            raise ValueError("feedback_per_question must be list")


    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI"
        )

    return response_json
















