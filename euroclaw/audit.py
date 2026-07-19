"""Append-only structured audit log.

Every governance-relevant event (tool execution, HITL decision, RBAC denial,
sandbox run) is written as one JSON line with a monotonic sequence number and a
chained hash of the previous record, giving a tamper-evident local ledger. For
regulated deployments, point ``AUDIT_DIR`` at WORM storage or ship the OTLP
spans to an immutable backend.
"""

import hashlib
import json
import logging
import os
import threading
import time

from euroclaw.settings import current_settings

logger = logging.getLogger("euroclaw.audit")

_lock = threading.Lock()
_last_hash = "0" * 64


def _audit_path() -> str:
    directory = current_settings().audit_dir
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "audit.jsonl")


def record(event_type: str, **fields) -> dict:
    """Append an audit record; returns the written record."""
    global _last_hash
    with _lock:
        payload = {
            "ts": time.time(),
            "event": event_type,
            **fields,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        chained = hashlib.sha256((_last_hash + canonical).encode("utf-8")).hexdigest()
        payload["prev_hash"] = _last_hash
        payload["hash"] = chained
        _last_hash = chained
        try:
            with open(_audit_path(), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload) + "\n")
        except Exception as exc:  # noqa: BLE001 - never let auditing crash a request
            logger.error("Failed to write audit record: %s", exc)
        return payload
