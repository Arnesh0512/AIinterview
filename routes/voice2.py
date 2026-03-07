from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from openai import OpenAI
from database import audio_interview_collection, audio_fs
from verify.token import verify_access_token
from verify.candidate import verify_candidate_payload
from utils.reader import OPENAP_API_KEY
import tempfile
import os
import json
import traceback
import subprocess
import time
import threading
import psutil
import whisper
from faster_whisper import WhisperModel

router = APIRouter(prefix="/voice", tags=["Voice Interview"])
security = HTTPBearer()

client = OpenAI(api_key=OPENAP_API_KEY)

process = psutil.Process(os.getpid())

# -----------------------------
# Load models once
# -----------------------------

print("Loading Whisper models...")
whisper_base = whisper.load_model("base")
whisper_small = whisper.load_model("small")

print("Loading Faster-Whisper models...")
fw_base = WhisperModel("base", device="cpu")
fw_small = WhisperModel("small", device="cpu")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


print("All speech models loaded.")

# -----------------------------
# Audio conversion
# -----------------------------

def convert_to_wav(input_path: str):

    wav_path = input_path + ".wav"

    subprocess.run([
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        wav_path
    ], check=True)

    return wav_path

#-----------------------------
# Evaluator
#-----------------------------
def evaluate(question, transcript):
    evaluation_prompt = f"""
    You are a strict interview evaluator.

    Question:
    {question}

    Candidate Spoken Answer:
    {transcript}

    Evaluate:
    - Technical accuracy
    - Clarity
    - Confidence
    - Depth

    Return strictly JSON:
    {{
        "analysis": "detailed feedback",
        "score": 0-10
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": evaluation_prompt}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    result = json.loads(response.choices[0].message.content)
    analysis = result.get("analysis")
    score = result.get("score")
    return(analysis, score)





# -----------------------------
# Benchmark helper
# -----------------------------

def benchmark_model(name, func, question):

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

    transcript = func()

    end = time.perf_counter()

    running = False
    monitor_thread.join()

    avg_cpu = sum(cpu_samples)/len(cpu_samples) if cpu_samples else 0

    analysis, score = evaluate(question, transcript)



    return {
        "model": name,
        "transcript": transcript,
        "time_sec": round(end - start, 3),
        "cpu_percent": round(avg_cpu,2),
        "peak_memory_mb": round(peak_memory / (1024*1024),2),
        "analysis": analysis,
        "score":score

    }

# -----------------------------
# Whisper
# -----------------------------

def run_whisper(model, wav_path):

    result = model.transcribe(wav_path, fp16=False)

    return result["text"]

# -----------------------------
# Faster Whisper
# -----------------------------

def run_faster_whisper(model, wav_path):

    segments, _ = model.transcribe(wav_path)

    text = ""

    for seg in segments:
        text += seg.text

    return text

# -----------------------------
# API
# -----------------------------




@router.post("/submit")
async def submit_audio_answer(
    question: str = Form(...),
    audio: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    temp_audio_path = None
    wav_path = None

    try:

        print("===== BENCHMARK START =====")

        token = credentials.credentials
        payload = verify_access_token(token)
        candidate, candidate_id, email = verify_candidate_payload(payload)

        suffix = os.path.splitext(audio.filename)[1] or ".webm"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:

            audio_bytes = await audio.read()
            temp_audio.write(audio_bytes)
            temp_audio_path = temp_audio.name

        wav_path = convert_to_wav(temp_audio_path)

        results = []


        results.append(benchmark_model("whisper-base",
            lambda: run_whisper(whisper_base, wav_path)))

        results.append(benchmark_model("whisper-small",
            lambda: run_whisper(whisper_small, wav_path)))


        results.append(benchmark_model("faster-whisper-base",
            lambda: run_faster_whisper(fw_base, wav_path)))

        results.append(benchmark_model("faster-whisper-small",
            lambda: run_faster_whisper(fw_small, wav_path)))


        # OpenAI transcription

        with open(wav_path,"rb") as f:

            start=time.perf_counter()
            resp = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=f
            )
            end=time.perf_counter()

            transcript = resp.text
            analysis, score = evaluate(question, transcript)


            results.append({
                "model":"openai-gpt4o-mini-transcribe",
                "transcript":resp.text,
                "time_sec":round(end-start,3),
                "cpu_percent": 0,
                "peak_memory_mb":0,
                "analysis": analysis,
                "score":score
            })


#############################################
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

        return {"results":results,
                "audio_session_id": str(inserted.inserted_id)}

##################################################




    except Exception as e:

        traceback.print_exc()

        raise HTTPException(status_code=500, detail=str(e))

    finally:

        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)




























