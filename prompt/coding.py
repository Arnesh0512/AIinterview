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
          "question_id": 1,
          "feedback": "...",
          "score": 8
        }
      ],
      "overall_feedback": "...",
      "overall_score": 7.5
    }
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
                                "question_id": {"type": "integer"},
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