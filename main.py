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

import circle_bender

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

finalist_file_path = "./input/singapore.txt"
if os.path.exists(finalist_file_path):
    with open(finalist_file_path, "r", encoding="utf-8") as file:
        finalists_content = file.read()


@app.post("/ask-llm")
async def ask_llm(question: str = Form(...)):
    try:
        prompt = f"Question: {question}"

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content":  "You are an assistant named Bender."
                                              "Answer in the style of a Bender from a cartoon."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = completion.choices[0].message.content

        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)}


def generate_wallet_id_and_address(project_name: str):
    """Generate wallet_id and wallet_address using the email as a base."""
    wallet_id, wallet_address = circle_bender.initialize_wallet(project_name, project_name, project_name)
    return wallet_id, wallet_address

@app.post("/ask-llm-with-context")
async def ask_llm(question: str = Form(...)):
    try:
        # additional_info = "Additional information would be added here."
        prompt = f"Question: {question}"

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an assistant  named Bender. Your role is to help hackers"
                                              " to win in hackathon and answer questions about hackathon."
                                              "Answer in the style of a Bender from a cartoon."
                                              "Using the information about past hackathon winners to answer the question."
                                              "Info about winners: finalists_content"},
                {"role": "user", "content": prompt}
            ]
        )
        answer = completion.choices[0].message.content

        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)}


@app.post("/register-project")
async def register_project(project: str = Form(...)):
    try:
        if not project:
            raise HTTPException(status_code=400, detail="Project name is required")

        # Generate wallet ID and address
        wallet_id, wallet_address = generate_wallet_id_and_address(project)
        execution_result = circle_bender.call_contract_execution(project, wallet_address)

        return {
            "wallet_id": wallet_id,
            "wallet_address": wallet_address,
            "ens_address": execution_result
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/generate-ens")
async def generate_ens(name: str = Form(...), address: str = Form(...)):
    try:
        if not name or not address:
            raise HTTPException(status_code=400, detail="Name and address are required")

        # Call the contract execution function
        execution_result = circle_bender.call_contract_execution(name, address)

        return {"execution_result": execution_result}
    except Exception as e:
        return {"error": str(e)}


# Start the app
if __name__ == "__main__":
    uvicorn.run("main:app", host="164.92.123.157", port=8282, reload=True)
