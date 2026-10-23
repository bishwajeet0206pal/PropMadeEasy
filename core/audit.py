import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List
from core.models import AuditLogEntry

class AuditLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "audit_trail.jsonl")
        self.in_memory_logs: List[AuditLogEntry] = []

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
        
        # Append to immutable JSONL file
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
            
        return entry

    def get_logs_for_entity(self, entity_id: str) -> List[AuditLogEntry]:
        return [log for log in self.in_memory_logs if log.entity_id == entity_id]

    def get_all_logs(self) -> List[AuditLogEntry]:
        return self.in_memory_logs
