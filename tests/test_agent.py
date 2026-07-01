from app.agent import detect_blockers, normalize_ids
from app.models import AgentInput, ProposalOutput


def test_detect_blockers_requires_core_proposal_facts():
    questions = detect_blockers(AgentInput(eventName="Workshop"))
    ids = {item["id"] for item in questions}

    assert "eventName" not in ids
    assert {"preparedBy", "eventDate", "venue", "objective", "itinerary"}.issubset(ids)


def test_normalized_proposal_validates_existing_frontend_shape():
    proposal = normalize_ids(
        {
            "title": "AI Day",
            "clientName": "Director",
            "projectTitle": "AI Day",
            "preparedBy": "Alex",
            "date": "2026-07-01",
            "status": "draft",
            "metadata": {},
            "sections": [
                {
                    "title": "Executive Summary",
                    "content": "Summary",
                    "subsections": [{"title": "Objective", "content": "Learn AI"}],
                }
            ],
        }
    )

    parsed = ProposalOutput.model_validate(proposal)
    assert parsed.sections[0].id == "executive-summary"
    assert parsed.sections[0].subsections[0].id == "objective"
