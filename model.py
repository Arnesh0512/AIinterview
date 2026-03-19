from openai import OpenAI
from utils.reader import OPENAI_API_KEY
import whisper
from faster_whisper import WhisperModel
import wave


CHATGPT = OpenAI(api_key=OPENAI_API_KEY)

def call_chatgpt(prompt: str, content: str, temperature: float, response_format: dict):

    response = CHATGPT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content}
        ],
        response_format=response_format,
        temperature=temperature
    )

    return response







































###############################################

# CHAT GPT 4o

###############################################

def call_audio_model_1(wav_path):

    with open(wav_path, "rb") as f:

        resp = CHATGPT.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=f
        )

    transcript = resp.text

    # compute duration
    with wave.open(wav_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        duration = frames / float(rate)

    segmented_data = [{
        "start": 0,
        "end": round(duration, 2),
        "text": transcript
    }]

    return segmented_data, transcript






























###############################################

# WHISPER BASE

###############################################

def call_audio_model_2(wav_path):
    whisper_base = whisper.load_model("base")
    result = whisper_base.transcribe(
        wav_path,
        fp16=False,
        language="en",
        beam_size=5
    )

    transcript = result["text"]
    segments = result["segments"]

    segmented_data = []

    for seg in segments:
        segment = {
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip()
        }
        segmented_data.append(segment)

    return segmented_data, transcript






























###############################################

# WHISPER SMALL

###############################################

def call_audio_model_3(wav_path):
    whisper_small = whisper.load_model("small")
    result = whisper_small.transcribe(
        wav_path,
        fp16=False,
        language="en",
        beam_size=5
    )

    transcript = result["text"]
    segments = result["segments"]

    segmented_data = []

    for seg in segments:
        segment = {
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip()
        }
        segmented_data.append(segment)

    return segmented_data, transcript






























###############################################

# FASTER WHISPER BASE

###############################################

def call_audio_model_4(wav_path):
    fw_base = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = fw_base.transcribe(
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

    return segmented_data, transcript































###############################################

# FASTER WHISPER SMALL

###############################################
def call_audio_model_5(wav_path):
    fw_small = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = fw_small.transcribe(
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

    return segmented_data, transcript