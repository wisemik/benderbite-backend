from typing import List

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
import uvicorn
# Assuming you're using OpenAI's library
import openai
import logging
import os
from pydantic import BaseModel

# Additional imports for database functionality
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

# Import your circle_bender module
import circle_bender

load_dotenv()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

app = FastAPI()
# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your frontend URL in production
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

        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an assistant named Bender."
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

        completion = openai.ChatCompletion.create(
            model="gpt-4",
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


@app.post("/leaderboard")
async def leaderboard():
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
                balance = 0  # Set balance to 0 if there's an error fetching it

            project_list.append({
                "name": project.name,
                "wallet_id": project.wallet_id,
                "wallet_address": project.wallet_address,
                "ens_address": project.ens_address,
                "balance": balance
            })

        # Sort the project list by balance in descending order
        sorted_project_list = sorted(project_list, key=lambda x: float(x['balance']), reverse=True)

        return {"leaderboard": sorted_project_list}
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


class WinnerProjects(BaseModel):
    winner_project_names: List[str]


@app.post("/pay-to-luckies")
async def pay_to_luckies(winner_projects: WinnerProjects):
    """
    Select winners, collect funds from each project's wallets, calculate the total amount,
    divide it among the winners, and pay each winner their share.
    """
    winner_project_names = winner_projects.winner_project_names
    try:
        logger.info(f"pay_to_luckies called with winner_project_names: {winner_project_names}")
        db = SessionLocal()

        # Retrieve all projects from the database
        projects = db.query(Project).all()
        logger.debug(f"Retrieved projects from database: {[project.name for project in projects]}")

        for winner_name in winner_project_names:
            winner_project = db.query(Project).filter(Project.name == winner_name).first()
            if not winner_project:
                logger.error(f"There is no project with such name: {winner_name}")
                return {"error": f"There is no project with such name: {winner_name}"}
            else:
                logger.debug(f"Found winner project in database: {winner_project.name}")

        # Collect funds from each project's wallets
        total_amount = 0.0
        for project in projects:
            logger.info(f"Processing project: {project.name}")
            # Get the wallet balance
            balance = circle_bender.wallet_balance(project.wallet_id)
            logger.debug(f"Wallet balance for {project.name} (wallet_id: {project.wallet_id}): {balance}")
            balance_amount = float(balance)
            if balance_amount > 0:
                logger.info(f"Transferring {balance} from {project.name} to master wallet")
                # Transfer balance from the project's wallet to the master wallet
                transfer_result = circle_bender.pay_to_master(balance, project.wallet_id)
                logger.debug(f"Transfer result for {project.name}: {transfer_result}")
                total_amount += balance_amount
            else:
                logger.info(f"No balance to transfer for {project.name}")

        logger.info(f"Total amount collected: {total_amount}")

        if not winner_project_names:
            logger.error("No winner project names provided.")
            raise HTTPException(status_code=400, detail="No winner project names provided.")

        # Calculate the amount per winner
        amount_per_winner = total_amount / len(winner_project_names)
        logger.info(f"Amount per winner: {amount_per_winner}")

        payments = []  # List to store the payments

        # Pay each winner their share
        for winner_name in winner_project_names:
            logger.info(f"Processing payment for winner: {winner_name}")
            # Get the winner's project details
            winner_project = db.query(Project).filter(Project.name == winner_name).first()

            payment_result = circle_bender.pay_to_winner(
                amount=str(amount_per_winner),
                winner_address=winner_project.wallet_address
            )
            logger.debug(f"Payment result for {winner_name}: {payment_result}")
            payments += payment_result

        logger.info(f"Payments completed: {payments}")
        return {"winners": payments}
    except Exception as e:
        logger.exception("An error occurred in pay_to_luckies")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# Start the app
if __name__ == "__main__":
    uvicorn.run("main:app", host="164.92.123.157", port=8282, reload=True)
