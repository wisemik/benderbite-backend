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

# Additional imports for database functionality
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

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

# Database setup using SQLite
DATABASE_URL = "sqlite:///./projects.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    wallet_id = Column(String)
    wallet_address = Column(String)
    ens_address = Column(String)

# Create the database tables
Base.metadata.create_all(bind=engine)

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
                                               "Answer in the style of Bender from a cartoon."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = completion.choices[0].message.content

        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)}

def generate_wallet_id_and_address(project_name: str):
    """Generate wallet_id and wallet_address using the project name as a base."""
    wallet_id, wallet_address = circle_bender.initialize_wallet(project_name, project_name, project_name)
    return wallet_id, wallet_address

@app.post("/ask-llm-with-context")
async def ask_llm_with_context(question: str = Form(...)):
    try:
        prompt = f"Question: {question}"

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an assistant named Bender. Your role is to help hackers "
                                               "win hackathons and answer questions about hackathons. "
                                               "Answer in the style of Bender from a cartoon. "
                                               f"Using the information about past hackathon winners to answer the question. "
                                               f"Info about winners: {finalists_content}"},
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
        ens_address = execution_result  # Assuming the execution result is the ENS address

        # Save the project to the database
        db = SessionLocal()
        db_project = Project(
            name=project,
            wallet_id=wallet_id,
            wallet_address=wallet_address,
            ens_address=ens_address
        )
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        db.close()

        return {
            "wallet_id": wallet_id,
            "wallet_address": wallet_address,
            "ens_address": ens_address
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/list-projects")
async def list_projects():
    try:
        db = SessionLocal()
        projects = db.query(Project).all()
        db.close()

        project_list = []
        for project in projects:
            try:
                # Fetch the balance using the wallet_id
                balance = circle_bender.wallet_balance(project.wallet_id)
            except Exception as e:
                balance = "Error fetching balance"

            project_list.append({
                "name": project.name,
                "wallet_id": project.wallet_id,
                "wallet_address": project.wallet_address,
                "ens_address": project.ens_address,
                "balance": balance  # Include the balance in the response
            })

        return {"projects": project_list}
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
