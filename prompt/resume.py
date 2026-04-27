from fastapi import HTTPException
from model import call_chatgpt
import json
from utils.resume import extract_text_with_ocr, extract_text_without_ocr


def process_resume(pdf_path, ocr_mode="N"):

    if ocr_mode.upper() == "Y":
        extracted_text = extract_text_with_ocr(pdf_path)
    else:
        extracted_text = extract_text_without_ocr(pdf_path)

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text extracted from PDF."
        )

    prompt = f""" You are a professional technical resume analyzer. Analyze the resume and:
      - Identify technical skills and tools
      - Summarize key projects and impact
      - Infer strengths and experience level
      - Suggest possible interview focus areas 
      - Point out weak or unclear areas 
      
      Output strictly in this format: 
      - Professional Summary (less than 300 words) 
      - Technical Skills - Key Projects & Impact 
      - Strength Areas 
      - Interview Focus Areas 
      - Weak / Missing Areas 
      Be concise, professional, and factual. 
      Do not add information not present in the resume. 
      Return only one complete string as summary no json summary or any other format."""

    content = f"Resume Content:\n{extracted_text}"

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "resume_summary",
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

    return summary_str







def generate_resume_question(
    summary_text: str,
    num_questions: int,
    previous_sessions: list
):


    prompt = f"""
You are a senior technical interviewer conducting a multi-round adaptive interview.

You will receive:
1) Resume Summary
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
  → Cover major technical skills from the resume.
  → Ensure broad coverage.

- If Previous Sessions contains data:
  → Each key represents one completed session.
  → session_1 is the most recent session.
  → Higher session numbers are older sessions.
  → Each session contains question-answer mappings.
  → You must:
      - Avoid repeating previous questions
      - Identify weak or shallow answers
      - Identify strong areas
      - Identify untouched skills from the resume
      - Increase overall difficulty progressively
      - Focus more on:
            * Weak areas
            * Partially answered topics
            * Important but previously unasked areas
            * Depth expansion in strong areas

Question Generation Rules:
- Generate exactly {num_questions} questions.
- Each list item must contain ONLY ONE question.
- Do NOT combine multiple questions into one.
- Include a mix of conceptual, practical, and system design questions where appropriate.
- Ensure increasing difficulty order within this round.
- Questions must be strictly relevant to the resume.
- Do NOT mention previous sessions explicitly in the question text.
- Do NOT provide answers.
- Do NOT add explanations.

Return strictly valid JSON in this format:
{{"questions": ["q1", "q2", ..., "qn"]}}
"""

    content = f"""
Resume Summary:
{summary_text}

Previous Sessions:
{json.dumps(previous_sessions, indent=2)}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "question_output",
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






def evaluate_resume_answers(summary_text: str, question_bank: list):

    prompt = """
    You are a senior technical interviewer evaluating candidate answers based on his resume summary.

    Evaluate each answer based on:
    - Technical correctness
    - Depth of understanding
    - Clarity of explanation
    - Relevance to the question

    Scoring Rules:
    - Score each answer from 0 to 10
    - Be strict but fair
    - Provide constructive feedback
    - Give overall feedback and overall score (0-10)

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
    Resume Summary:
    {summary_text}

    Question & Answers:
    {json.dumps(question_bank, indent=2)}
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "resume_evaluation_output",
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
                            "required": ["question_number", "feedback", "score"]
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



def generate_resume_combined_diff_session_feedback(summary_text: str, session_data: dict):

    prompt = """
You are a senior technical interview evaluator.

You will receive:
1) Candidate Resume Summary
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
- Each key inside a session represents a question, and its value is the candidate's answer.

Instructions:
- Evaluate overall technical progression across sessions.
- Identify improvement patterns.
- Identify repeated weaknesses.
- Identify consistent strengths.
- Evaluate depth growth and conceptual maturity.
- Compare recent performance vs older performance.
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
    Resume Summary:
    {summary_text}

    Session wise Question & Answers:
    {json.dumps(session_data, indent=2)}
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "resume_combined_feedback_output",
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
        raise HTTPException(status_code=500, detail="Invalid JSON returned by AI")
    




def generate_resume_combined_same_session_feedback(summary_text: str, session_data: dict):

    prompt = """
You are a senior technical interview evaluator.

You will receive:
1) Candidate Resume Summary
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
- Each key inside a session represents a question, and its value is the candidate's answer.
- All sessions correspond to the same interview round repeated over time.

Instructions:
- Evaluate progression across reattempts.
- Identify areas of improvement.
- Identify areas where mistakes persist.
- Identify conceptual clarity growth.
- Compare latest attempt with older attempts.
- Evaluate depth improvement and correction of past weaknesses.
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
    Resume Summary:
    {summary_text}

    Session wise Question & Answers:
    {json.dumps(session_data, indent=2)}
    """

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "resume_combined_feedback_output",
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
        raise HTTPException(status_code=500, detail="Invalid JSON returned by AI")