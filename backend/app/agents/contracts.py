"""
Shared data contracts for Manager ↔ Specialist agent communication.

These dataclasses define the structured I/O protocol used by all agents.
No agent-to-agent conversation — only structured task handoff and result return.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IntentType(Enum):
    CALENDAR_QUERY = "calendar_query"
    IMPORTANT_DATE = "important_date"
    DINNER_SUGGESTION = "dinner_suggestion"
    DATE_NIGHT = "date_night"
    MEMORY_SAVE = "memory_save"
    GENERAL = "general"
    BLOCKED = "blocked"


@dataclass
class AgentTask:
    task_id: str
    task_type: str          # matches IntentType values
    family_id: str
    requested_by: str       # "manager"
    inputs: dict
    context: dict
    constraints: list[str]
    timestamp: str


@dataclass
class AgentResult:
    task_id: str
    task_type: str
    agent: str              # "organizer" | "chef" | "date_planner" | "manager"
    success: bool
    data: dict
    confidence: str         # "high" | "medium" | "low"
    data_sources: list[str]
    warnings: list[str]
    timestamp: str


@dataclass
class ConversationTurn:
    turn_id: int
    role: str               # "user" | "assistant"
    content: str
    timestamp: str
    agent_calls: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)


@dataclass
class IntentClassification:
    intent: IntentType
    date_range: dict | None         # {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} or None
    member_filter: list[str] | None # member names/IDs or None (all members)
    reference_type: str | None      # "follow_up" | "date" | "person" | None
    confidence: str                 # "high" | "medium" | "low"
