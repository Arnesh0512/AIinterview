from model import call_chatgpt
from typing import List
import json
from fastapi import HTTPException

def generate_summary(resume_text):


    prompt = f""" 
    You are a professional technical resume analyzer. Analyze the resume and:
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

    content = f"Resume Content:\n{resume_text}"

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














def evaluate_resume_score(
        resume_text, resume_questions,
        company: str, role: str, skills: List[str]
):

    questions_text = "\n".join(
        f"{qid}. {q}" for qid, q in resume_questions.items()
    )

    prompt = """
You are a senior technical interviewer.

You will receive:

1) Candidate Resume
2) Interview Questions
3) Company Name, Role, and Required Skills.

For EACH question:
Evaluate whether the resume shows evidence that the candidate could answer it.

Scoring rules:
- Score each question from 0 to 10
- 0 = no evidence in resume
- 10 = strong clear evidence
- Base scores only on resume content
- Do NOT assume missing information
- Provide actionable feedback

Also provide:
- Overall feedback

IMPORTANT:
- Do not hallucinate missing answers
- Evaluate only based on given response
- Return strictly valid JSON

{
  "results":
    [
        {
        "question_id":"string",
        "feedback": "string",
        "score":number
        }, ....
    ],
    "overall_feedback": "string"
}
"""

    content = f"""
Resume:
{resume_text}

Questions:
{questions_text}

Company: {company}
Role: {role}
Skills: {", ".join(skills)}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "resume_scores",
            "schema": {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_id": {"type": "string"},
                                "feedback": {"type": "string"},
                                "score": {"type": "number"}
                            },
                            "required": [
                                "question_id",
                                "feedback",
                                "score"
                            ]
                        }
                    },
                    "overall_feedback": {"type": "string"}
                },
                "required": [
                    "results",
                    "overall_feedback"
                ]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.2, response_format)

    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)
        return response_json

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI for Resume evaluation"
        )



def evaluate_coding_score(evaluation_input):

    prompt = """
You are a senior coding interviewer.

You will receive list of such dictionaries
{"question_id": ,"problem_description":, "answer": ,"language": }

Evaluate each solution.

Scoring rules:
Score each question from 0 to 10
0 = completely wrong or no answer
10 = correct and optimal
Provide actionable feedback also

Also provide:
- Overall feedback

IMPORTANT:
- Do not hallucinate missing answers
- Evaluate only based on given response
- Return strictly valid JSON

{
  "results":
    [
        {
        "question_id":"string",
        "feedback": "string",
        "score":number
        }, ....
    ],
    "overall_feedback": "string"
}
"""

    content = json.dumps(evaluation_input, indent=2)

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "coding_scores",
            "schema": {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_id": {"type": "string"},
                                "feedback": {"type": "string"},
                                "score": {"type": "number"}
                            },
                            "required": [
                                "question_id",
                                "feedback",
                                "score"
                            ]
                        }
                    },
                    "overall_feedback": {"type": "string"}
                },
                "required": [
                    "results",
                    "overall_feedback"
                ]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.2, response_format)

    try:

        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)
        return response_json

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI for Coding evaluation"
        )
    



def evaluate_concept_score(evaluation_input):


    prompt = """
You are a senior technical interviewer.

You will receive list of such dictionaries
{"question_id": ,"question":, "answer": }



Evaluate each solution.

Scoring rules:
Score each question from 0 to 10
0 = completely wrong or no answer
10 = conceptually correct and optimal
Score each question independently.
Provide actionable feedback also

Also provide:
- Overall feedback

IMPORTANT:
- Do not hallucinate missing answers
- Evaluate only based on given response
- Return strictly valid JSON

{
  "results":
    [
        {
        "question_id":"string",
        "feedback": "string",
        "score":number
        }, ....
    ],
    "overall_feedback": "string"
}
"""

    content = json.dumps(evaluation_input, indent=2)

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "concept_scores",
            "schema": {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_id": {"type": "string"},
                                "feedback": {"type": "string"},
                                "score": {"type": "number"}
                            },
                            "required": [
                                "question_id",
                                "feedback",
                                "score"
                            ]
                        }
                    },
                    "overall_feedback": {"type": "string"}
                },
                "required": [
                    "results",
                    "overall_feedback"
                ]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.2, response_format)
 
    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)
        return response_json

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI for Concept evaluation"
        )


def evaluate_hr_score(evaluation_input, resume_summary):

    prompt = """
You are a senior HR interviewer evaluating candidate responses.

You will receive a list of dictionaries in the following format:

{
 "question_id": "string",
 "question": "string",
 "transcript": [
   {"start": number, "end": number, "text": "spoken text"},
   ...
 ]
}

For question_id "1" the question will be:
"Introduce Yourself"

For this question you will also receive a candidate resume summary.

Evaluation criteria:

1. Communication clarity
2. Confidence (use speaking duration and pacing)
3. Relevance to the question
4. Professional tone
5. Completeness of the response

Confidence analysis rule:
- Longer pauses or very short answers may indicate low confidence
- Smooth continuous speech with moderate pacing indicates higher confidence

For question_id "1":
- Evaluate whether the candidate introduction aligns with the resume summary.

Scoring rules:
Score each question from 0 to 10
0 = no response or irrelevant answer  
10 = confident, structured, and highly relevant response  
Score each question independently.

Provide actionable feedback also

Also provide:
- Overall feedback

IMPORTANT:
- Do not hallucinate missing answers
- Evaluate only based on given response
- Return strictly valid JSON

{
  "results":
    [
        {
        "question_id":"string",
        "feedback": "string",
        "score":number
        }, ....
    ],
    "overall_feedback": "string"
}
"""

    # attach resume summary only for intro question
    payload = {
        "resume_summary": resume_summary,
        "responses": evaluation_input
    }

    content = json.dumps(payload, indent=2)

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "hr_scores",
            "schema": {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_id": {"type": "string"},
                                "feedback": {"type": "string"},
                                "score": {"type": "number"}
                            },
                            "required": [
                                "question_id",
                                "feedback",
                                "score"
                            ]
                        }
                    },
                    "overall_feedback": {"type": "string"}
                },
                "required": [
                    "results",
                    "overall_feedback"
                ]
            }
        }
    }

    response = call_chatgpt(prompt, content, 0.2, response_format)

    try:
        response_content = response.choices[0].message.content
        response_json = json.loads(response_content)
        return response_json

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Invalid JSON returned by AI for HR evaluation"
        )