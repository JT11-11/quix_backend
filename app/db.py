from __future__ import annotations

import json
import os
import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .models import AgentInput, AgentRun


def get_conn() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(database_url, row_factory=dict_row)


def ensure_schema() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists public.proposal_agent_runs (
                  id uuid primary key,
                  user_id text not null,
                  proposal_id uuid,
                  status text not null default 'running'
                    check (status in ('running', 'waiting_for_input', 'completed', 'failed')),
                  input_context jsonb not null default '{}'::jsonb,
                  followup_questions jsonb not null default '[]'::jsonb,
                  followup_answers jsonb not null default '{}'::jsonb,
                  final_output jsonb,
                  error text,
                  created_at timestamptz not null default now(),
                  updated_at timestamptz not null default now()
                )
                """
            )
            cur.execute(
                """
                create index if not exists proposal_agent_runs_user_updated_idx
                  on public.proposal_agent_runs (user_id, updated_at desc)
                """
            )
            cur.execute(
                """
                create table if not exists public.proposal_agent_steps (
                  id uuid primary key,
                  run_id uuid not null references public.proposal_agent_runs(id) on delete cascade,
                  step_name text not null,
                  status text not null default 'pending'
                    check (status in ('pending', 'running', 'completed', 'failed')),
                  message text not null default '',
                  payload jsonb not null default '{}'::jsonb,
                  created_at timestamptz not null default now(),
                  updated_at timestamptz not null default now()
                )
                """
            )
            cur.execute(
                """
                create index if not exists proposal_agent_steps_run_created_idx
                  on public.proposal_agent_steps (run_id, created_at)
                """
            )
            cur.execute(
                """
                create table if not exists public.proposals (
                  id uuid primary key,
                  user_id text not null,
                  title text not null,
                  client_name text not null default '',
                  project_title text not null default '',
                  prepared_by text not null default '',
                  proposal_date date not null default current_date,
                  status text not null default 'draft' check (status in ('draft', 'complete')),
                  metadata jsonb not null default '{}'::jsonb,
                  sections jsonb not null default '[]'::jsonb,
                  created_at timestamptz not null default now(),
                  updated_at timestamptz not null default now()
                )
                """
            )
            cur.execute(
                """
                create index if not exists proposals_user_updated_idx
                  on public.proposals (user_id, updated_at desc)
                """
            )


def create_run(user_id: str, input_data: AgentInput) -> str:
    run_id = str(uuid.uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.proposal_agent_runs (id, user_id, status, input_context)
                values (%s, %s, 'running', %s::jsonb)
                """,
                (run_id, user_id, json.dumps(input_data.model_dump(mode="json"))),
            )
    return run_id


def get_run(run_id: str, user_id: str | None = None) -> AgentRun | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            params: tuple[Any, ...]
            if user_id:
                params = (run_id, user_id)
                cur.execute(
                    """
                    select id::text, user_id, proposal_id::text, status, input_context,
                      followup_questions, followup_answers, final_output, error,
                      created_at::text, updated_at::text
                    from public.proposal_agent_runs
                    where id = %s and user_id = %s
                    limit 1
                    """,
                    params,
                )
            else:
                cur.execute(
                    """
                    select id::text, user_id, proposal_id::text, status, input_context,
                      followup_questions, followup_answers, final_output, error,
                      created_at::text, updated_at::text
                    from public.proposal_agent_runs
                    where id = %s
                    limit 1
                    """,
                    (run_id,),
                )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                """
                select id::text, step_name, status, message, payload, created_at::text, updated_at::text
                from public.proposal_agent_steps
                where run_id = %s
                order by created_at asc
                """,
                (run_id,),
            )
            steps = cur.fetchall()
    return AgentRun(
        id=row["id"],
        userId=row["user_id"],
        proposalId=row["proposal_id"],
        status=row["status"],
        inputContext=row["input_context"] or {},
        followupQuestions=row["followup_questions"] or [],
        followupAnswers=row["followup_answers"] or {},
        finalOutput=row["final_output"],
        error=row["error"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
        steps=[
            {
                "id": step["id"],
                "stepName": step["step_name"],
                "status": step["status"],
                "message": step["message"],
                "payload": step["payload"] or {},
                "createdAt": step["created_at"],
                "updatedAt": step["updated_at"],
            }
            for step in steps
        ],
    )


def add_step(run_id: str, step_name: str, status: str, message: str, payload: dict[str, Any] | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.proposal_agent_steps (id, run_id, step_name, status, message, payload)
                values (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (str(uuid.uuid4()), run_id, step_name, status, message, json.dumps(payload or {})),
            )
            cur.execute(
                "update public.proposal_agent_runs set updated_at = now() where id = %s",
                (run_id,),
            )


def set_waiting(run_id: str, questions: list[dict[str, str]]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.proposal_agent_runs
                set status = 'waiting_for_input',
                    followup_questions = %s::jsonb,
                    updated_at = now()
                where id = %s
                """,
                (json.dumps(questions), run_id),
            )


def merge_answers(run_id: str, answers: dict[str, str]) -> AgentInput:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select input_context, followup_answers
                from public.proposal_agent_runs
                where id = %s
                limit 1
                """,
                (run_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Run not found")
            input_context = row["input_context"] or {}
            all_answers = {**(row["followup_answers"] or {}), **answers}
            for key, value in answers.items():
                if value and key in input_context:
                    input_context[key] = value
            cur.execute(
                """
                update public.proposal_agent_runs
                set status = 'running',
                    input_context = %s::jsonb,
                    followup_answers = %s::jsonb,
                    updated_at = now()
                where id = %s
                """,
                (json.dumps(input_context), json.dumps(all_answers), run_id),
            )
    return AgentInput.model_validate(input_context)


def set_failed(run_id: str, error: str) -> None:
    add_step(run_id, "Failed", "failed", error)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.proposal_agent_runs
                set status = 'failed', error = %s, updated_at = now()
                where id = %s
                """,
                (error, run_id),
            )


def save_final(run_id: str, user_id: str, proposal: dict[str, Any]) -> str:
    proposal_id = str(uuid.uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.proposals (
                  id, user_id, title, client_name, project_title, prepared_by,
                  proposal_date, status, metadata, sections, created_at, updated_at
                )
                values (
                  %s, %s, %s, %s, %s, %s, %s, %s,
                  %s::jsonb, %s::jsonb, now(), now()
                )
                """,
                (
                    proposal_id,
                    user_id,
                    proposal["title"],
                    proposal.get("clientName", ""),
                    proposal.get("projectTitle", proposal["title"]),
                    proposal.get("preparedBy", ""),
                    proposal.get("date"),
                    proposal.get("status", "draft"),
                    json.dumps(proposal.get("metadata", {})),
                    json.dumps(proposal.get("sections", [])),
                ),
            )
            cur.execute(
                """
                update public.proposal_agent_runs
                set status = 'completed',
                    proposal_id = %s,
                    final_output = %s::jsonb,
                    updated_at = now()
                where id = %s
                """,
                (proposal_id, json.dumps(proposal), run_id),
            )
    return proposal_id
