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
import whisper
from faster_whisper import WhisperModel


router = APIRouter(prefix="/voice", tags=["Voice Interview"])
security = HTTPBearer()

client = OpenAI(api_key=OPENAP_API_KEY)


# -----------------------------
# Load models once
# -----------------------------

print("Loading Whisper models...")
whisper_base = whisper.load_model("base")
whisper_small = whisper.load_model("small")

print("Loading Faster-Whisper models...")
fw_base = WhisperModel("base", device="cpu")
fw_small = WhisperModel("small", device="cpu")

print("All speech models loaded.")


# -----------------------------
# GPT evaluation
# -----------------------------

def evaluate(question, transcript):

    prompt = f"""
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
 "score": number
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    result = json.loads(response.choices[0].message.content)

    return result.get("analysis"), result.get("score")


# -----------------------------
# OpenAI transcription
# -----------------------------

def run_openai_transcription(wav_path, question):

    with open(wav_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=f
        )

    transcript = resp.text

    segmented_data = [{
        "start": 0,
        "end": None,
        "text": transcript
    }]

    print("\n--- OpenAI Segments ---")
    print(segmented_data)

    analysis, score = evaluate(question, transcript)

    return {
        "model": "openai-gpt4o-mini-transcribe",
        "transcript": transcript,
        "segmented_data": segmented_data,
        "analysis": analysis,
        "score": score
    }


# -----------------------------
# Whisper
# -----------------------------

def run_whisper(model, wav_path, question, model_name):

    result = model.transcribe(
        wav_path,
        fp16=False,
        language="en",
        beam_size=5
    )

    transcript = result["text"]
    segments = result["segments"]

    print(f"\n--- {model_name} Segments ---")
    for s in segments:
        print(s)

    segmented_data = []

    for seg in segments:

        segment = {
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip()
        }

        segmented_data.append(segment)

    print(segmented_data)


    analysis, score = evaluate(question, transcript)

    return {
        "model": model_name,
        "transcript": transcript,
        "segmented_data": segmented_data,
        "analysis": analysis,
        "score": score
    }


# -----------------------------
# Faster-Whisper with strong VAD
# -----------------------------

def run_faster_whisper(model, wav_path, question, model_name):

    segments, _ = model.transcribe(
        wav_path,
        beam_size=5,
        language="en",
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=300,   # detects shorter pauses
            speech_pad_ms=200
        )
    )

    segmented_data = []
    transcript = ""

    for seg in segments:

        segment = {
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip()
        }

        segmented_data.append(segment)
        transcript += seg.text + " "

    transcript = transcript.strip()

    print(f"\n--- {model_name} Segments ---")
    for s in segmented_data:
        print(s)

    analysis, score = evaluate(question, transcript)

    return {
        "model": model_name,
        "transcript": transcript,
        "segmented_data": segmented_data,
        "analysis": analysis,
        "score": score
    }


# -----------------------------
# GPT-4o audio transcription + evaluation
# -----------------------------

def run_gpt4o_audio_evaluation(wav_path, question):

    with open(wav_path, "rb") as f:
        audio_bytes = f.read()

    prompt = f"""
You are a strict technical interview evaluator.

1) Transcribe the audio.
2) Evaluate the answer.

Question:
{question}

Return JSON:

{{
 "transcript":"text",
 "analysis":"evaluation",
 "score": number
}}
"""
    try:
        
        response = client.responses.create(
            model="gpt-4o-audio-preview",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "audio": audio_bytes, "format": "wav"},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
        )

        raw_text = response.output[0].content[0].text

        print("\n--- GPT-4o raw output ---")
        print(raw_text)

    
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        result = json.loads(raw_text[start:end])

        transcript = result.get("transcript")

        segmented_data = [{
            "start": 0,
            "end": None,
            "text": transcript
        }]

        result = {
            "transcript": raw_text,
            "analysis": "Could not parse evaluation",
            "score": 0
        }

        return {
            "model": "gpt-4o-audio-evaluator",
            "transcript": transcript,
            "segmented_data": segmented_data,
            "analysis": result.get("analysis"),
            "score": result.get("score")
        }
    

    except Exception:
        print("GPT-4o JSON parse failed")
        




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
        print(1)
        results.append(run_faster_whisper(fw_base, wav_path, question, "faster-whisper-base"))
        print(2)
        results.append(run_faster_whisper(fw_small, wav_path, question, "faster-whisper-small"))
        print(3)
        results.append(run_whisper(whisper_base, wav_path, question, "whisper-base"))
        print(4)
        results.append(run_whisper(whisper_small, wav_path, question, "whisper-small"))
        print(5)
        results.append(run_openai_transcription(wav_path, question))
        print(6)
        results.append(run_gpt4o_audio_evaluation(wav_path, question))

        print("\n===== All Results =====")
        print(json.dumps(results, indent=2))

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