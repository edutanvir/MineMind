# test_gemini.py
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client()  # reads GEMINI_API_KEY from the environment
print([m.name for m in client.models.list() if "gemini" in m.name][:15])
r = client.models.generate_content(
    model=os.environ["GEMINI_MODEL"],
    contents="Reply exactly: MineMind Gemini connection works.")
print(r.text)
