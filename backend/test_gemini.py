import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("No API Key found")
    exit(1)

genai.configure(api_key=api_key)

models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
print("Supported models:", models)

try:
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
    response = model.generate_content("Hello, world!")
    print("Response from gemini-1.5-flash-latest:", response.text)
except Exception as e:
    print("Error with gemini-1.5-flash-latest:", e)

try:
    model2 = genai.GenerativeModel("gemini-1.5-flash")
    response2 = model2.generate_content("Hello, world!")
    print("Response from gemini-1.5-flash:", response2.text)
except Exception as e:
    print("Error with gemini-1.5-flash:", e)
