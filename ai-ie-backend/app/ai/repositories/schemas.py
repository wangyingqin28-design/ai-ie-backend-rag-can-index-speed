from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatRecord:
    role: str
    content: str
    timestamp: datetime


@dataclass
class SessionMetadata:
    session_id: str
    title: str
    created_at: float
    last_active: float


@dataclass
class SessionSummary:
    session_id: str
    title: str
    created_at: float
    last_active: float
    message_count: int
