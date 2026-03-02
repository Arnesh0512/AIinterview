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
2) Previous Interview Sessions (list format)

IMPORTANT INTERPRETATION RULES:

- If Previous Sessions is an empty list ([]):
  → This means this is the FIRST interview round.
  → Generate foundational to intermediate level questions.
  → Cover major technical skills from the resume.
  → Ensure broad coverage.

- If Previous Sessions contains data:
  → This means previous interview rounds already happened.
  → Each session contains questions and the candidate's answers.
  → You must:
      - Avoid repeating previous questions
      - Identify weak or shallow answers
      - Identify strong areas
      - Identify untouched skills from the resume
      - Increase overall difficulty progressively
      - Focus more on:
            * Weak areas
            * Partially answered questions
            * Important but previously unasked topics

Question Generation Rules:
- Generate exactly {num_questions} questions.
- Each list item must contain ONLY ONE question.
- Do not combine multiple questions into one.
- Include a mix of conceptual and practical/system design questions.
- Ensure increasing difficulty order within this round.
- Questions must be relevant to the resume.
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
            "name": "evaluation_output",
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



def generate_combined_diff_session_feedback(summary_text: str, session_data: dict):

    prompt = """
You are a senior technical interview evaluator.

You will receive multiple completed interview sessions.
Each session contains question-answer pairs.
You will also receive candidate resume summary, answers must be based on it.

Sessions are provided as a dictionary:
{
  "session_i": [
      {"question": "...", "answer": "..."},
      ...
  ],
  ...
}

Instructions:
- Evaluate overall technical progression
- Identify improvement patterns
- Identify repeated weaknesses
- Identify strengths
- Evaluate depth growth across sessions
- Be strict and analytical
- Provide professional structured feedback
- Do NOT mention JSON or formatting

Return strictly valid JSON:
{
  "feedback": "detailed combined feedback"
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
            "name": "combined_feedback_output",
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
        raise HTTPException(status_code=500, detail="Invalid JSON returned by AI")
    




def generate_combined_same_session_feedback(summary_text: str, session_data: dict):

    prompt = """
You are a senior technical interview evaluator.

You will receive multiple completed interview sessions.
Each session contains question-answer pairs.
All sessions provided are same session they are just reattempted over time,
latest session is in starting ,oldest session is in last 
You will also receive candidate resume summary, answers must be based on it.

Sessions are provided as a dictionary:
{
  "session_i_numx": [
      {"question": "...", "answer": "..."},
      ...
  ],
  ...
}
smaller the numx is more latest it is

Instructions:
- Evaluate overall technical progression
- Identify improvement patterns
- Identify repeated weaknesses
- Identify strengths
- Evaluate depth growth across sessions
- Be strict and analytical
- Provide professional structured feedback
- Do NOT mention JSON or formatting

Return strictly valid JSON:
{
  "feedback": "detailed combined feedback"
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
            "name": "combined_feedback_output",
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
        raise HTTPException(status_code=500, detail="Invalid JSON returned by AI")