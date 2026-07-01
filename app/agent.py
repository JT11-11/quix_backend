from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .models import AgentInput, AiConfig, ProposalOutput, ProposalSection


DEFAULT_SECTIONS = [
    ("executive-summary", "Executive Summary"),
    ("publicity", "Publicity"),
    ("programme-flow", "Programme Flow"),
    ("proposed-program", "Proposed Program"),
    ("organising-committee", "Organising Committee"),
    ("budget-list", "Budget List"),
    ("safety-emergency", "Safety and Emergency"),
    ("acknowledgement", "Acknowledgement"),
]


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def detect_blockers(input_data: AgentInput) -> list[dict[str, str]]:
    required = [
        ("eventName", "What is the official event name?"),
        ("preparedBy", "Who is preparing or submitting this proposal?"),
        ("eventDate", "What is the event date or date range?"),
        ("venue", "What venue or location should the proposal use?"),
        ("objective", "What is the main objective of the event?"),
        ("itinerary", "What is the programme flow or itinerary? A rough outline is enough."),
    ]
    payload = input_data.model_dump()
    questions: list[dict[str, str]] = []
    for key, label in required:
        if not clean_text(payload.get(key)):
            questions.append({"id": key, "label": label})
    return questions


def build_llm(ai: AiConfig) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=ai.apiKey,
        model=ai.model,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.25,
        default_headers={
            "HTTP-Referer": os.getenv("APP_REFERER", "http://localhost:3000"),
            "X-Title": "Quix Proposal Agent",
        },
    )


def proposal_prompt(input_data: AgentInput) -> list[Any]:
    schema_hint = {
        "title": "Official event proposal title",
        "clientName": "Addressee name",
        "projectTitle": "Event name",
        "preparedBy": "Submitter name",
        "date": "YYYY-MM-DD proposal submission date",
        "status": "draft",
        "metadata": {},
        "sections": [
            {
                "id": "executive-summary",
                "title": "Executive Summary",
                "content": "Optional section intro",
                "subsections": [
                    {"id": "background-objective", "title": "Background & Objective", "content": "Proposal-ready text"}
                ],
                "tables": [],
                "images": [],
            }
        ],
    }
    return [
        SystemMessage(
            content=(
                "You write formal school event proposals. Return only valid JSON. "
                "Never invent exact dates, venues, budgets, names, approvals, or quantities. "
                "Use concise proposal-ready language. Keep content suitable for approval."
            )
        ),
        HumanMessage(
            content=(
                "Create a complete proposal using this exact JSON-compatible shape:\n"
                f"{json.dumps(schema_hint, indent=2)}\n\n"
                "Required top-level sections and ids:\n"
                f"{json.dumps(DEFAULT_SECTIONS, indent=2)}\n\n"
                "Use the supplied poster/image metadata in relevant Publicity/Posters sections. "
                "Include compact tables for programme flow, budget, manpower, and risks when useful. "
                "Every section must have proposal-ready content or subsections.\n\n"
                "Input context:\n"
                f"{json.dumps(input_data.model_dump(mode='json'), indent=2)}"
            )
        ),
    ]


def extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def uid() -> str:
    return str(uuid.uuid4())


def fallback_proposal(input_data: AgentInput) -> dict[str, Any]:
    images = [
        {
            "id": image.id or uid(),
            "name": image.name,
            "url": image.url or "",
            "key": image.key,
            "contentType": image.contentType,
            "size": image.size,
            "caption": image.caption or image.name,
        }
        for image in input_data.images
        if image.url
    ]
    event_bits = [clean_text(input_data.eventDate), clean_text(input_data.eventTime), clean_text(input_data.venue)]
    event_overview = "\n".join([bit for bit in event_bits if bit])
    sections = [
        {
            "id": "executive-summary",
            "title": "Executive Summary",
            "content": "",
            "subsections": [
                {
                    "id": "background-objective",
                    "title": "Background & Objective",
                    "content": input_data.objective,
                    "tables": [],
                    "images": [],
                },
                {
                    "id": "event-overview",
                    "title": "Event Overview",
                    "content": event_overview,
                    "tables": [],
                    "images": [],
                },
            ],
            "tables": [],
            "images": [],
        },
        {
            "id": "publicity",
            "title": "Publicity",
            "content": input_data.publicity or "Publicity materials and communications will be prepared for the target audience.",
            "subsections": [
                {
                    "id": "posters",
                    "title": "Posters",
                    "content": "Poster assets submitted for this proposal are attached for review.",
                    "tables": [],
                    "images": images,
                }
            ],
            "tables": [],
            "images": [],
        },
        {
            "id": "programme-flow",
            "title": "Programme Flow",
            "content": input_data.itinerary,
            "subsections": [],
            "tables": [],
            "images": [],
        },
        {
            "id": "proposed-program",
            "title": "Proposed Program",
            "content": input_data.notes,
            "subsections": [
                {"id": "venues", "title": "Venues to be Used/Booked", "content": input_data.venue, "tables": [], "images": []},
                {"id": "manpower", "title": "Manpower", "content": input_data.manpower, "tables": [], "images": []},
            ],
            "tables": [],
            "images": [],
        },
        {"id": "organising-committee", "title": "Organising Committee", "content": input_data.preparedBy, "subsections": [], "tables": [], "images": []},
        {"id": "budget-list", "title": "Budget List", "content": input_data.budget or "Budget details will be confirmed separately.", "subsections": [], "tables": [], "images": []},
        {"id": "safety-emergency", "title": "Safety and Emergency", "content": input_data.riskManagement or "Safety and emergency measures will be managed according to institution guidelines.", "subsections": [], "tables": [], "images": []},
        {"id": "acknowledgement", "title": "Acknowledgement", "content": "Submitted for review and approval.", "subsections": [], "tables": [], "images": []},
    ]
    return {
        "title": input_data.eventName,
        "clientName": input_data.toName,
        "projectTitle": input_data.eventName,
        "preparedBy": input_data.preparedBy,
        "date": input_data.submissionDate or date.today().isoformat(),
        "status": "draft",
        "metadata": metadata_for(input_data),
        "sections": sections,
    }


def metadata_for(input_data: AgentInput) -> dict[str, str]:
    return {
        "institution": input_data.institution,
        "companyName": input_data.school,
        "club": input_data.club,
        "toName": input_data.toName,
        "toTitle": input_data.toTitle,
        "toDepartment": input_data.toDepartment,
        "ccNames": input_data.ccNames,
        "fromName": input_data.preparedBy,
        "fromTitle": input_data.fromTitle,
        "fromDepartment": input_data.fromDepartment,
    }


def normalize_ids(proposal: dict[str, Any]) -> dict[str, Any]:
    for section in proposal.get("sections", []):
        section["id"] = clean_text(section.get("id")) or slug(section.get("title", "section"))
        section.setdefault("content", "")
        section["tables"] = normalize_tables(section.get("tables", []))
        section.setdefault("images", [])
        for subsection in section.get("subsections", []) or []:
            subsection["id"] = clean_text(subsection.get("id")) or slug(subsection.get("title", "subsection"))
            subsection.setdefault("content", "")
            subsection["tables"] = normalize_tables(subsection.get("tables", []))
            subsection.setdefault("images", [])
    return proposal


def normalize_tables(tables: Any) -> list[dict[str, Any]]:
    if not isinstance(tables, list):
        return []

    normalized = []
    for index, table in enumerate(tables):
        if not isinstance(table, dict):
            continue
        headers = table.get("headers") if isinstance(table.get("headers"), list) else []
        rows = table.get("rows") if isinstance(table.get("rows"), list) else []
        normalized.append(
            {
                **table,
                "id": clean_text(table.get("id")) or uid(),
                "title": clean_text(table.get("title")) or f"Table {index + 1}",
                "headers": [str(header).strip() for header in headers if str(header).strip()],
                "rows": [
                    [str(cell).strip() for cell in row]
                    for row in rows
                    if isinstance(row, list) and any(str(cell).strip() for cell in row)
                ],
            }
        )
    return normalized


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or uid()


def generate_proposal(input_data: AgentInput, ai: AiConfig) -> dict[str, Any]:
    llm = build_llm(ai)
    response = llm.invoke(proposal_prompt(input_data))
    content = response.content if isinstance(response.content, str) else json.dumps(response.content)
    parsed = extract_json(content)
    parsed["metadata"] = {**metadata_for(input_data), **(parsed.get("metadata") or {})}
    parsed.setdefault("title", input_data.eventName)
    parsed.setdefault("clientName", input_data.toName)
    parsed.setdefault("projectTitle", input_data.eventName)
    parsed.setdefault("preparedBy", input_data.preparedBy)
    parsed.setdefault("date", input_data.submissionDate or date.today().isoformat())
    parsed.setdefault("status", "draft")
    normalized = normalize_ids(parsed)
    return ProposalOutput.model_validate(normalized).model_dump(mode="json")
