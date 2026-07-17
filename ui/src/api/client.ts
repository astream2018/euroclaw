// Typed client for the EuroClaw orchestration API.
// All privileged calls carry the user's OIDC bearer token; the server
// re-authorizes every action (the UI holds no privilege of its own).

export interface Participant {
  name: string;
  role: string;
}

export interface OrchestrateRequest {
  text: string;
  roleplay?: { persona: string };
  conversation?: { participants: Participant[] };
}

export interface RunEvent {
  type?: string;
  ts?: number;
  run?: Run;
  error?: string;
}

export interface Run {
  run_id: string;
  status: "queued" | "running" | "completed" | "failed";
  result?: string | null;
  error?: string;
  events?: RunEvent[];
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

function authHeaders(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/healthz/readiness`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function startRun(
  token: string,
  body: OrchestrateRequest
): Promise<{ run_id: string; status: string }> {
  const res = await fetch(`${BASE}/api/v1/orchestrate`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`orchestrate failed: ${res.status}`);
  return res.json();
}

export async function getRun(runId: string): Promise<Run> {
  const res = await fetch(`${BASE}/api/v1/runs/${runId}`);
  if (!res.ok) throw new Error(`run not found: ${res.status}`);
  return res.json();
}

// Subscribe to the Server-Sent Events stream for a run. Returns an unsubscribe fn.
export function streamRun(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onDone: (run?: Run) => void
): () => void {
  const source = new EventSource(`${BASE}/api/v1/runs/${runId}/events`);
  source.onmessage = (msg) => {
    const data: RunEvent = JSON.parse(msg.data);
    onEvent(data);
    if (data.type === "final") {
      onDone(data.run);
      source.close();
    }
  };
  source.onerror = () => source.close();
  return () => source.close();
}

export async function resolveHitl(
  taskId: string,
  approved: boolean
): Promise<void> {
  await fetch(`${BASE}/api/v1/hitl/callback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, approved }),
  });
}
