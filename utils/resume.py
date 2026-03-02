import fitz
import pytesseract
from pdf2image import convert_from_path
from bson import ObjectId
from database import resume_question_collection



def extract_text_without_ocr(pdf_path):
    text = ""
    doc = fitz.open(pdf_path)
    for page in doc:
        text += page.get_text()
        
    return text


def extract_text_with_ocr(pdf_path):
    text = ""
    pages = convert_from_path(pdf_path, dpi=400)

    for page in pages:
        text += pytesseract.image_to_string(page)
        text += "\n"

    return text






def previous_session_questions(resume_id : ObjectId):
    previous_sessions=[]

    all_sessions = list(
        resume_question_collection.find(
            {"resume_id": resume_id},
            {
                "session_number": 1,
                "question_bank": 1,
                "timestamp": 1
            }
        )
    )

    latest_sessions = {}

    for session in all_sessions:
        sn = session["session_number"]

        if (
            sn not in latest_sessions
            or session["timestamp"] > latest_sessions[sn]["timestamp"]
        ):
            latest_sessions[sn] = session

    sorted_sessions = sorted(
        latest_sessions.values(),
        key=lambda x: x["session_number"]
    )

    for session in sorted_sessions:
        qa_list = [
            {
                "question": q["question"],
                "answer": q["answer"]
            }
            for q in session.get("question_bank", [])
        ]

        previous_sessions.append({
            f"session_{session['session_number']}": qa_list
        })

    return previous_sessions
