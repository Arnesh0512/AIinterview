import json
from typing import List
from fastapi import HTTPException
from model import call_chatgpt


def generate_concept_topic_questions(
    topics: List[str],
    num_questions: int,
    previous_sessions: list
):

    prompt = f"""
    You are a senior computer science technical interviewer.

    Based on the given CS topics, generate {num_questions} 
    deep technical interview questions.

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
    - If Previous Sessions is an empty dictionary ({{}}):
    → This means this is the FIRST interview round.

    - If Previous Sessions contains data:
    → session_1 is the most recent session.
    → Higher session numbers represent older sessions.
    → Each key inside a session is a question and its value is the candidate’s answer.
    → You must:
        - Avoid repeating previous questions
        - Identify weak or shallow answers
        - Identify strong architectural understanding
        - Identify untouched components of the topic.
        - Increase overall difficulty progressively
        - Focus more on:
                * Weak explanations
                * Theory gaps
                * Edge cases not discussed
                * Indepth topic-level reasoning
                
    Questions should test:
    - Core conceptual understanding
    - Internal working
    - Design decisions
    - Trade-offs
    - Complexity analysis
    - Edge cases
    - Real-world application

    Question Generation Rules:
    - Generate exactly {num_questions} questions.
    - Each list item must contain ONLY ONE question.
    - Do NOT combine multiple questions into one.
    - Ensure increasing difficulty order within this round.
    - Questions must be highly specific to the repository.
    - Do NOT mention previous sessions explicitly in the question text.
    - Do NOT provide answers.
    - Do NOT add explanations.

    Output format:

    {{
        "questions": ["question1", "question2", ...]
    }}
    """

    content = f"""
    CS Topics:
    {", ".join(topics)}

    Previous Sessions:
    {json.dumps(previous_sessions, indent=2)}
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



def evaluate_concept_topic_answers(
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


def generate_concept_combined_diff_session_feedback(
    topics: list,
    session_data: dict
):

    prompt = """
You are a senior technical interview evaluator.

You will receive:
1) Selected conceptual topics
2) Multiple completed conceptual interview sessions.

Sessions are provided as a dictionary in this format:

{
    "session_1": {
        "Question text": "Answer text"
    },
    "session_2": {
        ...
    }
}

Interpretation Rules:

- session_1 is the most recent session.
- Higher session numbers represent older sessions.
- Each key inside a session is a question and its value is the candidate's answer.
- Sessions may contain different questions across rounds.

Instructions:

- Evaluate overall conceptual progression across sessions.
- Identify depth improvement in theoretical understanding.
- Identify repeated conceptual weaknesses.
- Identify consistent strengths.
- Evaluate clarity of explanation and correctness.
- Evaluate ability to connect concepts across topics.
- Compare recent sessions with older sessions.
- Be strict, analytical, and professional.
- Provide structured feedback including:
    * Strengths
    * Weaknesses
    * Progression analysis
    * Recommendations
- Do NOT mention JSON or formatting.

Return strictly valid JSON:
{
  "feedback": "detailed combined feedback"
}
"""

    content = f"""
Selected Topics:
{topics}

Session wise Question & Answers:
{json.dumps(session_data)}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "concept_combined_feedback_output",
            "schema": {
                "type": "object",
                "properties": {
                    "feedback": {"type": "string"}
                },
                "required": ["feedback"]
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
    


def generate_concept_combined_same_session_feedback(
    topics: list,
    session_data: dict
):

    prompt = """
You are a senior technical interview evaluator.

You will receive:
1) Selected conceptual topics
2) Multiple reattempts of the SAME conceptual interview session.

Sessions are provided as a dictionary in this format:

{
    "session_1": {
        "Question text": "Answer text"
    },
    "session_2": {
        ...
    }
}

Interpretation Rules:

- session_1 is the most recent attempt.
- Higher session numbers represent older attempts.
- All sessions correspond to the SAME question set.
- Only answers differ between attempts.

Instructions:

- Evaluate conceptual improvement across attempts.
- Identify corrections of previous misunderstandings.
- Identify persistent conceptual errors.
- Evaluate improvement in explanation clarity and structure.
- Evaluate depth growth in theoretical reasoning.
- Compare the latest attempt clearly with older attempts.
- Be strict, analytical, and professional.
- Provide structured feedback including:
    * Improvements observed
    * Remaining weaknesses
    * Conceptual maturity growth
    * Recommendations
- Do NOT mention JSON or formatting.

Return strictly valid JSON:
{
  "feedback": "detailed combined feedback"
}
"""

    content = f"""
Selected Topics:
{topics}

Session wise Question & Answers:
{json.dumps(session_data)}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "concept_combined_feedback_output",
            "schema": {
                "type": "object",
                "properties": {
                    "feedback": {"type": "string"}
                },
                "required": ["feedback"]
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













