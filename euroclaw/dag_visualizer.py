"""Renders an agent execution trace as a GitHub-compatible Mermaid diagram.

This is a *visualization* aid. The authoritative, tamper-evident record is the
structured audit log (:mod:`euroclaw.audit`) and OpenTelemetry spans.
"""

import os


class AgentDAGTracer:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.steps: list[tuple[str, str, str]] = []
        self.nodes: set[str] = set()

    def add_step(self, source: str, destination: str, action: str) -> None:
        self.steps.append((source, destination, action))
        self.nodes.add(source)
        self.nodes.add(destination)

    def export_to_markdown(self, output_dir: str = "audit_logs") -> str:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"trace_{self.task_id}.md")

        lines = [
            "### EuroClaw Agent Execution Trace",
            f"**Task ID:** `{self.task_id}`\n",
            "```mermaid",
            "graph TD;",
            "    classDef secure fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;",
            "    classDef danger fill:#ffebee,stroke:#d32f2f,stroke-width:2px;",
        ]
        for src, dest, action in self.steps:
            lines.append(f"    {src} -->|{action}| {dest};")
            if "Firecracker" in dest or "MicroVM" in dest or "Sandbox" in dest:
                lines.append(f"    class {dest} secure;")
        lines.append("```\n")

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return filepath
