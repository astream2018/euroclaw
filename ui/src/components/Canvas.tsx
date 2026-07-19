import { type DragEvent } from "react";
import { type Participant } from "../api/client";

// Minimal drag-and-drop orchestration canvas: drag an agent template from the
// palette onto the board to add it as a conversation participant. This is a
// scaffold — a production canvas would use a graph library (React Flow, etc.)
// and persist workflows via the API.

const PALETTE: Participant[] = [
  { name: "analyst", role: "product strategist" },
  { name: "reviewer", role: "risk reviewer" },
  { name: "engineer", role: "solutions architect" },
  { name: "compliance", role: "compliance officer" },
];

interface Props {
  persona: string;
  onPersonaChange: (value: string) => void;
  participants: Participant[];
  onParticipantsChange: (value: Participant[]) => void;
}

export function Canvas({
  persona,
  onPersonaChange,
  participants,
  onParticipantsChange,
}: Props) {
  function onDragStart(e: DragEvent<HTMLDivElement>, agent: Participant) {
    e.dataTransfer.setData("application/json", JSON.stringify(agent));
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const agent: Participant = JSON.parse(
      e.dataTransfer.getData("application/json")
    );
    if (!participants.some((p) => p.name === agent.name)) {
      onParticipantsChange([...participants, agent]);
    }
  }

  function removeAgent(name: string) {
    onParticipantsChange(participants.filter((p) => p.name !== name));
  }

  return (
    <div style={{ margin: "1rem 0" }}>
      <label>
        Facilitator persona
        <input
          style={{ width: "100%" }}
          value={persona}
          onChange={(e) => onPersonaChange(e.target.value)}
        />
      </label>

      <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
        <div style={{ flex: 1 }}>
          <strong>Agent palette</strong>
          {PALETTE.map((agent) => (
            <div
              key={agent.name}
              draggable
              onDragStart={(e) => onDragStart(e, agent)}
              style={{
                border: "1px solid #ccc",
                borderRadius: 6,
                padding: 8,
                margin: "6px 0",
                cursor: "grab",
                background: "#fafafa",
              }}
            >
              {agent.name} — {agent.role}
            </div>
          ))}
        </div>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          style={{
            flex: 2,
            minHeight: 160,
            border: "2px dashed #0288d1",
            borderRadius: 8,
            padding: 12,
            background: "#f2fbff",
          }}
        >
          <strong>Conversation board</strong>
          {participants.length === 0 && (
            <p style={{ color: "#888" }}>Drag agents here to add participants.</p>
          )}
          {participants.map((p) => (
            <div
              key={p.name}
              style={{
                border: "1px solid #0288d1",
                borderRadius: 6,
                padding: 8,
                margin: "6px 0",
                background: "#e1f5fe",
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <span>
                {p.name} — {p.role}
              </span>
              <button onClick={() => removeAgent(p.name)}>remove</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
