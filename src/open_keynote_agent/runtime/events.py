from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SessionEvent:
    def __init__(self, seq: int, type: str, payload: dict[str, Any]) -> None:
        self.seq = seq
        self.type = type
        self.ts = datetime.now(UTC).isoformat()
        self.payload = payload

    def to_dict(self) -> dict[str, Any]:
        return {"seq": self.seq, "type": self.type, "ts": self.ts, "payload": self.payload}


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._seq = 0
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, type: str, payload: dict[str, Any]) -> SessionEvent:
        event = SessionEvent(seq=self._seq, type=type, payload=payload)
        self._seq += 1
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), default=str, ensure_ascii=False) + "\n")
        return event
