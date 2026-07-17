"""Shared, distributed state backed by Redis with an in-memory fallback.

Everything that must survive across replicas lives here: rate-limit counters,
Human-in-the-Loop (HITL) approvals, and the async run/job store that powers the
non-blocking orchestration API. In multi-replica deployments Redis is required;
the in-memory fallback keeps single-process/dev and tests working when Redis is
unavailable, and logs loudly so the degradation is never silent.
"""

import json
import logging
import threading
import time

import redis

from euroclaw.settings import current_settings

logger = logging.getLogger("euroclaw.state")

_client: "redis.Redis | None" = None
_client_lock = threading.Lock()

# In-memory fallbacks (per-process only)
_mem_kv: dict[str, tuple[str, float | None]] = {}
_mem_rate: dict[str, tuple[int, float]] = {}
_mem_lock = threading.Lock()


def get_client() -> "redis.Redis | None":
    """Return a shared Redis client, or None if Redis cannot be reached."""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        s = current_settings()
        try:
            client = redis.Redis(
                host=s.redis_host,
                port=s.redis_port,
                password=s.redis_password or None,
                ssl=s.redis_use_tls,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=5,
            )
            client.ping()
            _client = client
            logger.info("Connected to Redis at %s:%s", s.redis_host, s.redis_port)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Redis unavailable (%s); using in-memory fallback (NOT safe for "
                "multi-replica deployments)",
                exc,
            )
            _client = None
        return _client


# --------------------------------------------------------------------------- #
# Generic key/value with TTL
# --------------------------------------------------------------------------- #
def kv_set(key: str, value: dict, ttl_seconds: int | None = None) -> None:
    client = get_client()
    raw = json.dumps(value)
    if client is not None:
        client.set(key, raw, ex=ttl_seconds)
        return
    with _mem_lock:
        expiry = time.time() + ttl_seconds if ttl_seconds else None
        _mem_kv[key] = (raw, expiry)


def kv_get(key: str) -> dict | None:
    client = get_client()
    if client is not None:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    with _mem_lock:
        entry = _mem_kv.get(key)
        if not entry:
            return None
        raw, expiry = entry
        if expiry is not None and expiry <= time.time():
            _mem_kv.pop(key, None)
            return None
        return json.loads(raw)


# --------------------------------------------------------------------------- #
# Rate limiting (fixed window, atomic on Redis)
# --------------------------------------------------------------------------- #
def rate_limit_hit(identity: str, limit: int, window_seconds: int) -> bool:
    """Return True if the caller is within the limit, False if throttled."""
    key = f"rl:{identity}"
    client = get_client()
    if client is not None:
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()
        return int(count) <= limit
    now = time.time()
    with _mem_lock:
        count, reset = _mem_rate.get(key, (0, now + window_seconds))
        if reset <= now:
            count, reset = 0, now + window_seconds
        count += 1
        _mem_rate[key] = (count, reset)
        return count <= limit


# --------------------------------------------------------------------------- #
# HITL approvals
# --------------------------------------------------------------------------- #
def hitl_set(task_id: str, payload: dict, ttl_seconds: int = 7200) -> None:
    kv_set(f"hitl:{task_id}", payload, ttl_seconds)


def hitl_get(task_id: str) -> dict | None:
    return kv_get(f"hitl:{task_id}")


# --------------------------------------------------------------------------- #
# Async run / job store
# --------------------------------------------------------------------------- #
def run_create(run_id: str, payload: dict, ttl_seconds: int = 86400) -> None:
    payload = {**payload, "events": []}
    kv_set(f"run:{run_id}", payload, ttl_seconds)


def run_get(run_id: str) -> dict | None:
    return kv_get(f"run:{run_id}")


def run_update(run_id: str, **fields) -> dict | None:
    run = run_get(run_id)
    if run is None:
        return None
    run.update(fields)
    kv_set(f"run:{run_id}", run)
    return run


def run_append_event(run_id: str, event: dict) -> None:
    run = run_get(run_id)
    if run is None:
        return
    events = run.get("events", [])
    events.append({**event, "ts": time.time()})
    run["events"] = events
    kv_set(f"run:{run_id}", run)


def reset_for_tests() -> None:
    """Clear in-memory fallbacks and any Redis test keys (test helper)."""
    with _mem_lock:
        _mem_kv.clear()
        _mem_rate.clear()
    client = get_client()
    if client is not None:
        for prefix in ("rl:", "hitl:", "run:"):
            for key in client.scan_iter(match=f"{prefix}*"):
                client.delete(key)
