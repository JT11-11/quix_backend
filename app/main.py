from __future__ import annotations

import os

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from . import db
from .agent import detect_blockers, generate_proposal
from .models import AnswerRequest, StartRunRequest

app = FastAPI(title="Quix Proposal Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_internal_secret(x_agent_secret: str | None) -> None:
    expected = os.getenv("AGENT_BACKEND_SECRET", "dev-secret")
    if not x_agent_secret or x_agent_secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.on_event("startup")
def startup() -> None:
    db.ensure_schema()


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


@app.post("/agent/runs")
def start_run(
    request: StartRunRequest,
    background_tasks: BackgroundTasks,
    x_agent_secret: str | None = Header(default=None),
):
    require_internal_secret(x_agent_secret)
    db.ensure_schema()
    run_id = db.create_run(request.userId, request.input)
    db.add_step(run_id, "Reviewing inputs", "completed", "I have the event details and materials.")

    questions = detect_blockers(request.input)
    if questions:
        db.add_step(
            run_id,
            "Checking missing details",
            "completed",
            "A few details are missing before I can write this accurately.",
            {"questions": questions},
        )
        db.set_waiting(run_id, questions)
        return db.get_run(run_id, request.userId)

    db.add_step(run_id, "Drafting sections", "running", "I’m writing the proposal sections now.")
    background_tasks.add_task(_complete_generation, run_id, request.userId, request.input, request.ai)
    return db.get_run(run_id, request.userId)


@app.get("/agent/runs/{run_id}")
def get_run(
    run_id: str,
    user_id: str = Query(...),
    x_agent_secret: str | None = Header(default=None),
):
    require_internal_secret(x_agent_secret)
    run = db.get_run(run_id, user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.post("/agent/runs/{run_id}/answers")
def answer_run(
    run_id: str,
    request: AnswerRequest,
    background_tasks: BackgroundTasks,
    x_agent_secret: str | None = Header(default=None),
):
    require_internal_secret(x_agent_secret)
    run = db.get_run(run_id, request.userId)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in ("waiting_for_input", "running"):
        raise HTTPException(status_code=409, detail=f"Run is {run.status}")

    input_data = db.merge_answers(run_id, request.answers)
    db.add_step(run_id, "Follow-up answers received", "completed", "Thanks, I can continue with the draft.")
    questions = detect_blockers(input_data)
    if questions:
        db.add_step(
            run_id,
            "Checking missing details",
            "completed",
            "I still need a little more context before writing.",
            {"questions": questions},
        )
        db.set_waiting(run_id, questions)
        return db.get_run(run_id, request.userId)

    db.add_step(run_id, "Drafting sections", "running", "I’m writing the proposal sections now.")
    background_tasks.add_task(_complete_generation, run_id, request.userId, input_data, request.ai)
    return db.get_run(run_id, request.userId)


def _complete_generation(run_id: str, user_id: str, input_data, ai) -> None:
    try:
        proposal = generate_proposal(input_data, ai)
        db.add_step(run_id, "Drafting sections", "completed", "The draft sections are ready.")
        db.add_step(run_id, "Saving proposal", "running", "I’m preparing the proposal for review.")
        proposal_id = db.save_final(run_id, user_id, proposal)
        db.add_step(
            run_id,
            "Saving proposal",
            "completed",
            "The proposal is ready to open.",
            {"proposalId": proposal_id},
        )
    except Exception as exc:
        db.set_failed(run_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
