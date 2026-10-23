import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from core.models import AuditLogEntry

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class AuditLogger:
    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            self.log_dir = os.path.join(_BASE_DIR, "logs")
        elif not os.path.isabs(log_dir):
            self.log_dir = os.path.join(_BASE_DIR, log_dir)
        else:
            self.log_dir = log_dir

        self.log_file: Optional[str] = None
        self.in_memory_logs: List[AuditLogEntry] = []

        try:
            os.makedirs(self.log_dir, exist_ok=True)
            self.log_file = os.path.join(self.log_dir, "audit_trail.jsonl")
        except (OSError, IOError):
            # Fall back to /tmp on serverless environments like Vercel/AWS Lambda
            try:
                self.log_dir = "/tmp/logs"
                os.makedirs(self.log_dir, exist_ok=True)
                self.log_file = os.path.join(self.log_dir, "audit_trail.jsonl")
            except Exception:
                self.log_file = None

    def record(self, actor: str, action: str, entity_type: str, entity_id: str, details: Dict[str, Any]) -> AuditLogEntry:
        entry = AuditLogEntry(
            log_id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            timestamp=datetime.now()
        )
        self.in_memory_logs.append(entry)
        
        # Append to immutable JSONL file if available
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(entry.model_dump_json() + "\n")
            except Exception:
                pass
            
        return entry

    def get_logs_for_entity(self, entity_id: str) -> List[AuditLogEntry]:
        return [log for log in self.in_memory_logs if log.entity_id == entity_id]

    def get_all_logs(self) -> List[AuditLogEntry]:
        return self.in_memory_logs
