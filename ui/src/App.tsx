import { useEffect, useState } from "react";
import {
  checkHealth,
  getRun,
  startRun,
  streamRun,
  type Participant,
  type Run,
  type RunEvent,
} from "./api/client";
import { Canvas } from "./components/Canvas";

export function App() {
  const [token, setToken] = useState(localStorage.getItem("ec_token") ?? "");
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [prompt, setPrompt] = useState("Draft a launch plan for the new feature");
  const [persona, setPersona] = useState("executive sponsor");
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    checkHealth().then(setHealthy);
  }, []);

  useEffect(() => {
    localStorage.setItem("ec_token", token);
  }, [token]);

  async function onRun() {
    setBusy(true);
    setEvents([]);
    setRun(null);
    try {
      const body = {
        text: prompt,
        roleplay: { persona },
        ...(participants.length ? { conversation: { participants } } : {}),
      };
      const { run_id } = await startRun(token, body);
      streamRun(
        run_id,
        (e) => setEvents((prev) => [...prev, e]),
        async (finished) => {
          setRun(finished ?? (await getRun(run_id)));
          setBusy(false);
        }
      );
    } catch (err) {
      setEvents((prev) => [...prev, { error: String(err) }]);
      setBusy(false);
    }
  }

  return (
    <div style={{ fontFamily: "system-ui", maxWidth: 1100, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>🇪🇺 EuroClaw Canvas</h1>
      <p style={{ color: healthy ? "green" : "crimson" }}>
        API status: {healthy === null ? "checking…" : healthy ? "ready" : "unavailable"}
      </p>

      <label>
        OIDC bearer token
        <input
          style={{ width: "100%", fontFamily: "monospace" }}
          value={token}
          placeholder="paste your access token"
          onChange={(e) => setToken(e.target.value)}
        />
      </label>

      <Canvas
        persona={persona}
        onPersonaChange={setPersona}
        participants={participants}
        onParticipantsChange={setParticipants}
      />

      <label>
        Prompt
        <textarea
          style={{ width: "100%", minHeight: 80 }}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
      </label>

      <button disabled={busy || !token} onClick={onRun} style={{ marginTop: 8 }}>
        {busy ? "Running…" : "Run workflow"}
      </button>

      <h3>Live events</h3>
      <pre style={{ background: "#f5f5f5", padding: 12, minHeight: 80 }}>
        {events.map((e) => JSON.stringify(e)).join("\n") || "(no events yet)"}
      </pre>

      {run && (
        <>
          <h3>Result ({run.status})</h3>
          <pre style={{ background: "#eef7ff", padding: 12 }}>
            {run.result ?? run.error ?? "(none)"}
          </pre>
        </>
      )}
    </div>
  );
}
