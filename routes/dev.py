from datetime import datetime, date, timezone
from database import candidate_collection, admin_collection
from verify.token import create_access_token
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from openai import OpenAI
from database import audio_interview_collection, audio_fs
from verify.token import verify_access_token
from verify.candidate import verify_candidate_payload
from utils.reader import OPENAI_API_KEY

import tempfile
import os
import json
import traceback
import time
import threading
import psutil

from model import call_audio_model_1
#from model import call_audio_model_2, call_audio_model_3
#from model import call_audio_model_4, call_audio_model_5


router = APIRouter(prefix="/dev", tags=["Dev Auth"])
security = HTTPBearer()



@router.post("/generate-candidate-token")
def generate_token(email: str):

    candidate = candidate_collection.find_one({"email": email.lower()})

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate_id = str(candidate["_id"])

    today=date.today()
    Year = today.year + (1 if today.month > 6 else 0)
    Month = 6
    Date = 30



    payload = {
        "candidate_id":candidate_id,
        "email": email,
        "role": "candidate",
        "exp": datetime(Year, Month, Date , 18,30, tzinfo=timezone.utc)
    }


    access_token = create_access_token(payload)

    return {access_token}





@router.post("/generate-admin-token")
def generate_token(email: str):

    admin = admin_collection.find_one({"email": email.lower()})

    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    admin_id = str(admin["_id"])

    today=date.today()
    Year = today.year + (1 if today.month > 6 else 0)
    Month = 6
    Date = 30


    payload = {
        "admin_id":str(admin_id),
        "email": email,
        "role": "admin",
        "exp": datetime(Year, Month, Date , 18,30, tzinfo=timezone.utc)
    }
    
    access_token = create_access_token(payload)

    return {access_token}









client = OpenAI(api_key=OPENAI_API_KEY)

process = psutil.Process(os.getpid())




# -----------------------------
# GPT evaluation
# -----------------------------

def evaluate(question, transcript, segmented_data):

    prompt = f"""
You are a strict interview evaluator.

Question:
{question}

Candidate Spoken Answer:
{transcript}

Segments of speech {{"start":"", "end":"", "text":""}}:
{segmented_data}
using this you can also guess the speed of candidate

Evaluate:
- Technical accuracy
- Clarity
- Confidence
- Depth

Return strictly JSON:

{{
 "analysis": "detailed feedback string",
 "score": number 0 to 10
}}
"""

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "transcript_analysis",
            "schema": {
                "type": "object",
                "properties": {
                    "analysis": {"type": "string"},
                    "score": {"type": "number"}
                },
                "required": [
                    "analysis",
                    "score"
                ]
            }
        }
    }

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format=response_format
    )

    result = json.loads(response.choices[0].message.content)

    return result.get("analysis"), result.get("score")




# -----------------------------
# Benchmark helper
# -----------------------------

def benchmark_model(name, func):

    peak_memory = 0
    cpu_samples = []
    running = True

    def monitor():

        nonlocal peak_memory

        while running:

            mem = process.memory_info().rss
            peak_memory = max(peak_memory, mem)

            cpu_samples.append(psutil.cpu_percent(interval=0.1))

    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.start()

    start = time.perf_counter()

    segmented_data, transcript = func()

    end = time.perf_counter()

    running = False
    monitor_thread.join()

    avg_cpu = sum(cpu_samples)/len(cpu_samples) if cpu_samples else 0

    return segmented_data, transcript, {
        "time_sec": round(end - start, 3),
        "cpu_percent": round(avg_cpu,2),
        "peak_memory_mb": round(peak_memory / (1024*1024),2)
    }




# -----------------------------
# API
# -----------------------------

@router.post("/voice/submit")
async def submit_audio_answer(
    question: str = Form(...),
    audio: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):


    temp_audio_path = None

    try:

        token = credentials.credentials
        payload = verify_access_token(token)
        candidate, candidate_id, email = verify_candidate_payload(payload)

        if not audio.filename.lower().endswith(".wav"):
            raise HTTPException(status_code=400, detail="Only WAV files allowed")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:

            audio_bytes = await audio.read()
            temp_audio.write(audio_bytes)
            temp_audio_path = temp_audio.name

        wav_path = temp_audio_path

        results = []

        print("\n===== Running Models =====")

        #model_list = [call_audio_model_1, call_audio_model_2, call_audio_model_3, call_audio_model_4, call_audio_model_5]
        #model_name = ["openai-gpt4o-mini-transcribe","whisper-base","whisper-small","faster-whisper-base","faster-whisper-small",]

        model_list = [call_audio_model_1]
        model_name = ["openai-gpt4o-mini-transcribe"]

        for i in range(len(model_list)):

            print("##########################################################")
            print(i+1)

            segmented_data, transcript, benchmark = benchmark_model(
                model_name[i],
                lambda: model_list[i](wav_path)
            )

            print(segmented_data)
            print(transcript)

            analysis, score = evaluate(question, transcript, segmented_data)

            results.append({
                "model": model_name[i],
                "transcript": transcript,
                "segmented_data": segmented_data,
                "analysis": analysis,
                "score": score,
                "benchmark": benchmark
            })

            print("##########################################################")
            print()

        
        # store audio
        with open(temp_audio_path, "rb") as f:
            audio_file_id = audio_fs.put(
                f,
                filename=audio.filename,
                content_type=audio.content_type
            )

        audio_doc = {
            "candidate_id": candidate_id,
            "question": question,
            "audio_file_id": audio_file_id,
            "results": results
        }

        inserted = audio_interview_collection.insert_one(audio_doc)

        return {
            "results": results,
            "audio_session_id": str(inserted.inserted_id)
        }

    except Exception as e:

        print("ERROR:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:

        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)