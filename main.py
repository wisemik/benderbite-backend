from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
import uvicorn
from openai import OpenAI
import logging
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Form

load_dotenv()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()
# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("ALLOWS_ORIGIN")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.post("/ask-llm")
async def ask_llm(question: str = Form(...)):
    try:
        additional_info = "Additional information would be added here."
        prompt = f"Question: {question}\n\nAdditional information:\n{additional_info}"

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = completion.choices[0].message.content

        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)}

# Start the app
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)