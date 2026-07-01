from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


AgentRunStatus = Literal["running", "waiting_for_input", "completed", "failed"]
StepStatus = Literal["pending", "running", "completed", "failed"]


class AgentImage(BaseModel):
    id: str | None = None
    name: str
    url: str | None = None
    key: str | None = None
    caption: str | None = None
    contentType: str | None = None
    size: int | None = None


class AgentInput(BaseModel):
    eventName: str = ""
    submissionDate: str | None = None
    preparedBy: str = ""
    fromTitle: str = ""
    fromDepartment: str = ""
    institution: str = "Nanyang Polytechnic"
    school: str = "School of Information Technology"
    club: str = "School of Information Technology Club 2026/27"
    toName: str = "Ms Tan Soon Keow"
    toTitle: str = "Director"
    toDepartment: str = "School of Information Technology"
    ccNames: str = "Mr Boon Seng Meng, Dr Veronica Lim"
    eventDate: str = ""
    eventTime: str = ""
    venue: str = ""
    targetAudience: str = ""
    objective: str = ""
    itinerary: str = ""
    budget: str = ""
    manpower: str = ""
    riskManagement: str = ""
    publicity: str = ""
    notes: str = ""
    images: list[AgentImage] = Field(default_factory=list)


class AiConfig(BaseModel):
    apiKey: str
    model: str


class StartRunRequest(BaseModel):
    userId: str
    input: AgentInput
    ai: AiConfig


class AnswerRequest(BaseModel):
    userId: str
    answers: dict[str, str]
    ai: AiConfig


class AgentStep(BaseModel):
    id: str
    stepName: str
    status: StepStatus
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class AgentRun(BaseModel):
    id: str
    userId: str
    proposalId: str | None = None
    status: AgentRunStatus
    inputContext: dict[str, Any]
    followupQuestions: list[dict[str, str]] = Field(default_factory=list)
    followupAnswers: dict[str, str] = Field(default_factory=dict)
    finalOutput: dict[str, Any] | None = None
    error: str | None = None
    createdAt: str
    updatedAt: str
    steps: list[AgentStep] = Field(default_factory=list)


class ProposalTable(BaseModel):
    id: str
    title: str | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ProposalImageOut(BaseModel):
    id: str
    name: str
    url: str
    key: str | None = None
    contentType: str | None = None
    size: int | None = None
    caption: str | None = None


class ProposalSubsection(BaseModel):
    id: str
    title: str
    content: str
    tables: list[ProposalTable] = Field(default_factory=list)
    images: list[ProposalImageOut] = Field(default_factory=list)


class ProposalSection(BaseModel):
    id: str
    title: str
    content: str = ""
    subsections: list[ProposalSubsection] = Field(default_factory=list)
    tables: list[ProposalTable] = Field(default_factory=list)
    images: list[ProposalImageOut] = Field(default_factory=list)
    notes: str | None = None


class ProposalOutput(BaseModel):
    title: str
    clientName: str = ""
    projectTitle: str
    preparedBy: str
    date: str = Field(default_factory=lambda: date.today().isoformat())
    status: Literal["draft", "complete"] = "draft"
    metadata: dict[str, Any] = Field(default_factory=dict)
    sections: list[ProposalSection]
