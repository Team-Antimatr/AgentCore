"""Layer 4: Immutable audit logger writing structured JSONL events."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class AuditEvent:
    """Structured record of every agent request and decision."""

    timestamp: str
    prompt: str
    guardrail_category: str
    tool_used: str
    status: str  # "ALLOWED", "BLOCKED", "ESCALATED"
    summary: str


class AuditLogger:
    """Appends immutable JSONL audit events to disk."""

    def __init__(self, log_path: Path | str = Path("logs/audit.jsonl")) -> None:
        self.log_path = Path(log_path)

    def log(
        self,
        prompt: str,
        guardrail_category: str,
        tool_used: str,
        status: str,
        summary: str,
    ) -> AuditEvent:
        """Write an audit record and return it."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            prompt=prompt,
            guardrail_category=guardrail_category,
            tool_used=tool_used,
            status=status,
            summary=summary,
        )
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event)) + "\n")
        return event

    def read_recent(self, limit: int = 10) -> list[dict]:
        """Return the most recent audit log entries."""
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:]]
