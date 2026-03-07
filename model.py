from openai import OpenAI
from utils.reader import OPENAP_API_KEY
import whisper
from faster_whisper import WhisperModel


CHATGPT = OpenAI(api_key=OPENAP_API_KEY)
whisper_base = whisper.load_model("base")
whisper_small = whisper.load_model("small")
fw_base = WhisperModel("base", device="cpu")
fw_small = WhisperModel("small", device="cpu")

def call_chatgpt(prompt: str, content: str, temperature: float, reponse_format: dict):

    response = CHATGPT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content}
        ],
        response_format=reponse_format,
        temperature=temperature
    )

    return response


def call_audio_model(wav_path):

    with open(wav_path, "rb") as f:

        resp = CHATGPT.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=f
        )

    transcript = resp.text

    segmented_data = [{
        "start": 0,
        "end": None,
        "text": transcript
    }]

    return segmented_data



def call_audio_model(wav_path):

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

    return segmented_data



def call_audio_model(wav_path):

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

    return segmented_data



def call_audio_model(wav_path):

    segments, _ = fw_base.transcribe(
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

    return segmented_data



def call_audio_model(wav_path):

    segments, _ = fw_small.transcribe(
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

    return segmented_data
