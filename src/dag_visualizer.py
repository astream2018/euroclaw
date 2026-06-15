# src/dag_tracer.py
import os


class AgentDAGTracer:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.steps = []
        self.nodes = set()

    def add_step(self, source: str, destination: str, action: str):
        """Logs a transition between two states or agents."""
        self.steps.append((source, destination, action))
        self.nodes.add(source)
        self.nodes.add(destination)

    def export_to_markdown(self, output_dir: str = "audit_logs"):
        """Generates a GitHub-compatible Mermaid markdown file."""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"trace_{self.task_id}.md")

        mermaid_code = [
            "### EuroClaw Agent Execution Trace",
            f"**Task ID:** `{self.task_id}`\n",
            "```mermaid",
            "graph TD;",
        ]

        # Add styles for specific sovereign components
        mermaid_code.append(
            "    classDef secure fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;"
        )
        mermaid_code.append(
            "    classDef danger fill:#ffebee,stroke:#d32f2f,stroke-width:2px;"
        )

        # Build the graph links
        for src, dest, action in self.steps:
            mermaid_code.append(f"    {src} -->|{action}| {dest};")

            # Auto-style the hardware sandbox nodes
            if "Firecracker" in dest or "MicroVM" in dest:
                mermaid_code.append(f"    class {dest} secure;")

        mermaid_code.append("```\n")

        with open(filepath, "w") as f:
            f.write("\n".join(mermaid_code))

        return filepath
