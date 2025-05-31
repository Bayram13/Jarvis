import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def ask_jarvis(message):
    response = openai.ChatCompletion.create(
        model="gpt-4",  # GPT-3.5 də istifadə oluna bilər
        messages=[
            {"role": "system", "content": "Sən ağıllı və nəzakətli virtual köməkçisən, adın Jarvisdir."},
            {"role": "user", "content": message}
        ]
    )
    return response['choices'][0]['message']['content']
