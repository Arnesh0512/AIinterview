import os
from datetime import datetime
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
import gridfs
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
from openai import OpenAI
from database import summary_collection, user_collection, client 

load_dotenv()

# Initialize OpenAI client
client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Import your existing DB config

db = client["interview"]
FS = gridfs.GridFS(db)

candidates_collection = user_collection
summaries_collection = summary_collection


# ---------------------------------------------------------
# Extract text WITHOUT OCR
# ---------------------------------------------------------
def extract_text_without_ocr(pdf_path):
    text = ""
    doc = fitz.open(pdf_path)
    for page in doc:
        text += page.get_text()
    return text


# ---------------------------------------------------------
# Extract text WITH OCR
# ---------------------------------------------------------
def extract_text_with_ocr(pdf_path):
    text = ""
    pages = convert_from_path(pdf_path, dpi=300)

    for page in pages:
        text += pytesseract.image_to_string(page)
        text += "\n"

    return text


# ---------------------------------------------------------
# Summarize using ChatGPT
# ---------------------------------------------------------
def summarize_resume(text):
    prompt = f"""
    Summarize the following resume in less than 200 words.
    Include skills, experience, projects, technologies, education and achievements.
    Provide a structured but concise professional summary.

    Resume:
    {text}
    """

    response = client_ai.chat.completions.create(
        model="gpt-4o-mini",   # cost-efficient + good reasoning
        messages=[
            {"role": "system", "content": "You are a professional resume analyzer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content


# ---------------------------------------------------------
# Main Function
# ---------------------------------------------------------
def process_resume(pdf_path, candidate_id, ocr_mode="N"):
    """
    pdf_path: path to resume pdf
    candidate_id: ObjectId of candidate
    ocr_mode: 'Y' or 'N'
    """

    if isinstance(candidate_id, str):
        candidate_id = ObjectId(candidate_id)

    # 1️⃣ Extract text
    if ocr_mode.upper() == "Y":
        extracted_text = extract_text_with_ocr(pdf_path)
    else:
        extracted_text = extract_text_without_ocr(pdf_path)

    if not extracted_text.strip():
        raise ValueError("No text extracted from PDF.")

    # 2️⃣ Summarize
    summary_text = summarize_resume(extracted_text)

    # 3️⃣ Store PDF in GridFS
    with open(pdf_path, "rb") as f:
        file_id = FS.put(
            f,
            filename=os.path.basename(pdf_path),
            content_type="application/pdf"
        )

    # 4️⃣ Store summary in summaries collection
    summary_doc = {
        "Candidate_id": candidate_id,
        "Summary": summary_text,
        "File_id": file_id,
        "created_at": datetime.now()
    }

    summary_insert_result = summaries_collection.insert_one(summary_doc)
    summary_object_id = summary_insert_result.inserted_id

    # 5️⃣ Update candidate collection
    candidates_collection.update_one(
        {"_id": candidate_id},
        {
            "$push": {
                "Resume": {
                    "summary_id": summary_object_id,
                    "timestamp": datetime.now()
                }
            }
        }
    )

    return {
        "summary_id": str(summary_object_id),
        "file_id": str(file_id),
        "summary": summary_text
    }