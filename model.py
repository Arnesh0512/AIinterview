from openai import OpenAI
from utils.reader import OPENAP_API_KEY

CHATGPT = OpenAI(api_key=OPENAP_API_KEY)

def call_chatgpt(prompt: str, content: str, temperature: float, reponse_format: dict):

    response = CHATGPT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content}
        ],
        response_format=reponse_format,  # 🔥 Global JSON mode
        temperature=temperature
    )

    return response