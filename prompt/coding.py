import json
from fastapi import HTTPException
from model import call_chatgpt


def evaluate_coding_answers(questions: list):

    prompt = """
    You are a senior technical coding interviewer.

    For each coding solution, evaluate:

    - Correctness of logic
    - Time complexity awareness
    - Space complexity awareness
    - Code structure and readability
    - Edge case handling

    Scoring Rules:
    - Score each question from 0 to 10
    - Be strict but fair
    - Penalize incorrect logic heavily
    - Reward optimal solutions
    - Provide clear and concise feedback

    Also provide:
    - Overall feedback
    - Overall score (0-10)

    Return strictly valid JSON in this format:

    {
      "feedback_per_question": [
        {
          "question_id": "1",
          "feedback": "...",
          "score": 8
        }
      ],
      "overall_feedback": "...",
      "overall_score": 7.5
    }

    -question_id provided in input should match in output 
    """

    content = f"""
    Coding Questions and Answers:

    {json.dumps(questions, indent=2)}
    """
    print(questions)

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "coding_evaluation_output",
            "schema": {
                "type": "object",
                "properties": {
                    "feedback_per_question": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_id": {"type": "string"},
                                "feedback": {"type": "string"},
                                "score": {"type": "number"}
                            },
                            "required": ["question_id", "feedback", "score"]
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

        if not isinstance(response_json.get("feedback_per_question"), list):
            raise ValueError("feedback_per_question must be list")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI"
        )

    return response_json


def generate_coding_combined_diff_session_feedback(session_data: dict):

    prompt = """
You are a senior coding interview evaluator.

You will receive multiple completed coding interview sessions.

Sessions are provided as a dictionary in this format:

{
    "session_1": {
        "Problem Description": "Language: X\nAnswer:\nCode"
    },
    "session_2": {
        ...
    }
}

Interpretation Rules:

- session_1 is the most recent session.
- Higher session numbers represent older sessions.
- Each key inside a session is the full problem description.
- The value contains the language used and the candidate's full answer.

Instructions:

- Evaluate overall coding progression across sessions.
- Analyze problem-solving approach maturity.
- Evaluate improvement in:
    * Algorithmic thinking
    * Code structure
    * Edge case handling
    * Optimization
    * Clarity and readability
- Identify repeated logical mistakes.
- Identify improvement in time/space complexity reasoning.
- Compare recent sessions with older sessions.
- Be strict and analytical.
- Provide structured feedback including:
    * Strengths
    * Weaknesses
    * Progression analysis
    * Recommendations for improvement
- Do NOT mention JSON or formatting.

Return strictly valid JSON:
{
  "feedback": "detailed combined feedback"
}
"""

    content = f"""
Session wise Coding Attempts:
{json.dumps(session_data, indent=2)}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "coding_combined_feedback_output",
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
    

def generate_coding_combined_same_session_feedback(session_data: dict):

    prompt = """
You are a senior coding interview evaluator.

You will receive multiple reattempts of the SAME coding interview session.

Sessions are provided as a dictionary in this format:

{
    "session_1": {
        "Problem Description": "Language: X\nAnswer:\nCode"
    },
    "session_2": {
        ...
    }
}

Interpretation Rules:

- session_1 is the most recent attempt.
- Higher session numbers represent older attempts.
- All sessions correspond to the SAME set of problems.
- Only answers and approaches may differ.

Instructions:

- Evaluate improvement across attempts.
- Analyze correction of previous mistakes.
- Evaluate improvement in:
    * Algorithm choice
    * Code efficiency
    * Edge case handling
    * Code readability
    * Use of appropriate data structures
- Identify persistent mistakes.
- Compare latest attempt with older attempts clearly.
- Evaluate whether complexity improved.
- Be strict and analytical.
- Provide structured feedback including:
    * Improvements observed
    * Remaining weaknesses
    * Technical maturity growth
    * Recommendations
- Do NOT mention JSON or formatting.

Return strictly valid JSON:
{
  "feedback": "detailed combined feedback"
}
"""

    content = f"""
Session wise Coding Attempts:
{json.dumps(session_data, indent=2)}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "coding_combined_feedback_output",
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